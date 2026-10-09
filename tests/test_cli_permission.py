from __future__ import annotations

import contextlib
import json
import hashlib
import io
import logging
import os
from pathlib import Path
import sys
import tempfile
import stat
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QTranslator
from PySide6.QtWidgets import QApplication, QWidget
from secretmanager import cli, ipc
from secretmanager.database.database import Database
from secretmanager.domain.secret import Secret
from secretmanager.ipc import (
    CliPermissionDeniedError,
    LocalSecretServer,
    request_secrets,
)
from secretmanager.repositories.sqlite_secret_repository import SqliteSecretRepository
from secretmanager.services.secret_service import SecretService
from secretmanager.ui.dialogs.secret_dialog import SecretDialog


class CliPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="cli-permission-")
        self.data_dir = Path(self.temp_dir.name)
        (self.data_dir / "config.json").write_text(
            json.dumps({"SecretManager": {"CliIntegrationEnabled": True}}),
            encoding="utf-8",
        )
        self.key = b"p" * 32
        self.database = Database(self.data_dir / "vault.db", self.key)
        self.database.create_tables()
        self.repository = SqliteSecretRepository(
            self.database.Session,
            lambda: self.key,
        )
        self.service = SecretService(self.repository)
        self.allowed_value = "allowed-secret-value-9f4b"
        self.denied_value = "denied-secret-value-2c1a"
        self.service.create(
            "CLI_ALLOWED",
            self.allowed_value,
            allow_cli=True,
        )
        self.service.create(
            "CLI_DENIED",
            self.denied_value,
        )
        self.server = LocalSecretServer(self.data_dir, self.service.get)
        self.server.start()

    def tearDown(self):
        self.server.close()
        self.database.close()
        self.temp_dir.cleanup()

    def test_permission_persists_and_defaults_to_denied(self):
        secret = self.service.create("CLI_DEFAULT", "default-value")
        self.assertFalse(secret.allow_cli)
        self.assertFalse(self.service.get("CLI_DEFAULT").allow_cli)

        updated = self.service.update(
            current_name="CLI_DEFAULT",
            name="CLI_DEFAULT",
            value="default-value",
            allow_cli=True,
        )
        self.assertTrue(updated.allow_cli)
        self.assertTrue(self.service.get("CLI_DEFAULT").allow_cli)

        retained = self.service.update(
            current_name="CLI_DEFAULT",
            name="CLI_DEFAULT",
            value="default-value",
        )
        self.assertTrue(retained.allow_cli)

        revoked = self.service.update(
            current_name="CLI_DEFAULT",
            name="CLI_DEFAULT",
            value="default-value",
            allow_cli=False,
        )
        self.assertFalse(revoked.allow_cli)
        self.assertFalse(self.service.get("CLI_DEFAULT").allow_cli)

    def test_allowed_secret_is_granted_and_denied_secret_is_not_returned(self):
        grants = request_secrets(self.data_dir, ["CLI_ALLOWED"])
        self.assertEqual(grants["CLI_ALLOWED"].value, self.allowed_value)

        response = self.server._handle_request({
            "operation": "get",
            "names": ["CLI_ALLOWED", "CLI_DENIED"],
        })
        self.assertEqual(response["error"], "cli_not_allowed")
        self.assertNotIn("secrets", response)
        with self.assertRaises(CliPermissionDeniedError):
            request_secrets(self.data_dir, ["CLI_ALLOWED", "CLI_DENIED"])

    def test_cli_does_not_launch_child_or_echo_value_when_permission_is_denied(self):
        stderr = io.StringIO()
        log_messages = []
        log_handler = logging.Handler()
        log_handler.emit = lambda record: log_messages.append(record.getMessage())
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)
        try:
            with (
                patch.object(cli, "get_data_dir", return_value=self.data_dir),
                patch.object(cli, "_run_child") as run_child,
                contextlib.redirect_stderr(stderr),
            ):
                result = cli.main([
                    "--use", "CLI_ALLOWED", "CLI_DENIED", "--",
                    sys.executable, "-c", "raise SystemExit(0)",
                ])
            self.assertEqual(result, 1)
            run_child.assert_not_called()
            emitted_text = stderr.getvalue() + "\n".join(log_messages)
            self.assertNotIn(self.allowed_value, emitted_text)
            self.assertNotIn(self.denied_value, emitted_text)
        finally:
            root_logger.removeHandler(log_handler)

    def test_simultaneous_clients_receive_only_their_requested_grants(self):
        self.service.create("CLI_SECOND", "second-value", allow_cli=True)
        names = [
            ["CLI_ALLOWED"],
            ["CLI_SECOND"],
            ["CLI_ALLOWED", "CLI_SECOND"],
            ["CLI_SECOND"],
        ]
        with ThreadPoolExecutor(max_workers=len(names)) as executor:
            results = list(executor.map(
                lambda requested: request_secrets(self.data_dir, requested),
                names,
            ))
        self.assertEqual(results[0]["CLI_ALLOWED"].value, self.allowed_value)
        self.assertEqual(results[1]["CLI_SECOND"].value, "second-value")
        self.assertEqual(
            {name: grant.value for name, grant in results[2].items()},
            {"CLI_ALLOWED": self.allowed_value, "CLI_SECOND": "second-value"},
        )
        self.assertEqual(results[3]["CLI_SECOND"].value, "second-value")

    def test_lock_cancels_cli_request_without_waiting_or_starting_child(self):
        entered_lookup = threading.Event()
        release_lookup = threading.Event()
        cli_finished = threading.Event()
        cli_result = {}
        stderr = io.StringIO()
        lifecycle_dir = self.data_dir / "lifecycle"
        lifecycle_dir.mkdir()
        (lifecycle_dir / "config.json").write_text(
            json.dumps({"SecretManager": {"CliIntegrationEnabled": True}}),
            encoding="utf-8",
        )

        def slow_lookup(_name):
            entered_lookup.set()
            release_lookup.wait(5)
            return SimpleNamespace(
                value="in-flight-secret-value",
                allow_cli=True,
                expires_on=None,
                expires_at_time=None,
            )

        server = LocalSecretServer(lifecycle_dir, slow_lookup)
        server.start()

        def invoke_cli():
            with (
                patch.object(cli, "get_data_dir", return_value=lifecycle_dir),
                patch.object(cli, "_run_child") as run_child,
                contextlib.redirect_stderr(stderr),
            ):
                cli_result["result"] = cli.main([
                    "--use", "IN_FLIGHT", "--",
                    sys.executable, "-c", "pass",
                ])
                cli_result["run_child"] = run_child.call_count
            cli_finished.set()

        client_thread = threading.Thread(target=invoke_cli)
        client_thread.start()
        try:
            self.assertTrue(entered_lookup.wait(2))
            close_started = time.monotonic()
            server.close()
            self.assertLess(time.monotonic() - close_started, 0.5)
            self.assertTrue(cli_finished.wait(2))
            self.assertEqual(cli_result["result"], 1)
            self.assertEqual(cli_result["run_child"], 0)
            self.assertIn("vault was locked or closed", stderr.getvalue())
            self.assertNotIn("in-flight-secret-value", stderr.getvalue())
        finally:
            release_lookup.set()
            client_thread.join(3)

        self.assertFalse(client_thread.is_alive())
        self.assertTrue(server.wait_closed(3))
        self.assertFalse((lifecycle_dir / ".ipc-token").exists())

    def test_secret_values_are_not_written_as_plaintext_files(self):
        for path in self.data_dir.rglob("*"):
            if not path.is_file():
                continue
            file_contents = path.read_bytes()
            self.assertNotIn(self.allowed_value.encode(), file_contents, path.name)
            self.assertNotIn(self.denied_value.encode(), file_contents, path.name)

    def test_ipc_token_is_written_for_authenticated_session(self):
        self.assertEqual(
            (self.data_dir / ".ipc-token").read_bytes(),
            self.server.token,
        )

    @unittest.skipIf(os.name == "nt", "Unix socket permissions are POSIX-specific")
    def test_unix_ipc_files_have_restricted_permissions(self):
        self.assertEqual(
            stat.S_IMODE((self.data_dir / ".ipc-token").stat().st_mode),
            0o600,
        )
        self.assertEqual(
            stat.S_IMODE(Path(self.server.address).stat().st_mode),
            0o600,
        )
    def test_fluent_dialog_exposes_switch_and_exact_tooltip(self):
        translator = QTranslator()
        catalog = ROOT / "src" / "secretmanager" / "localization" / "translations" / "secretmanager_es.qm"
        self.assertTrue(translator.load(str(catalog)))
        QApplication.instance().installTranslator(translator)
        parent = QWidget()
        parent.resize(600, 700)
        dialog = SecretDialog(parent)
        try:
            self.assertFalse(dialog.cli_permission.isChecked())
            self.assertEqual(
                dialog.cli_info_button.toolTip(),
                translator.translate(
                    "SecretManager",
                    "ui.when_enabled_this_secret_can_be_requested_and_used_f",
                ),
            )
            dialog.cli_permission.setChecked(True)
            self.assertTrue(dialog.get_data()["allow_cli"])
        finally:
            dialog.clear_sensitive_data()
            dialog.close()
            parent.close()
            QApplication.instance().removeTranslator(translator)


if __name__ == "__main__":
    unittest.main()

