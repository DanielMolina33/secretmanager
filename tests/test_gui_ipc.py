from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import threading
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secretmanager import cli
from secretmanager.ipc import IpcRequestCancelledError, request_secrets
from secretmanager.database.database import Database
from secretmanager.repositories.sqlite_secret_repository import SqliteSecretRepository
from secretmanager.services.secret_service import SecretService
from secretmanager.ui import main_window as main_window_module
from secretmanager.vault_manager import VaultManager


class _ThemeManagerStub:
    def __init__(self, _parent):
        pass

    def set_mode_from_index(self, _index):
        pass

    def apply_system_accent(self):
        pass

    def close(self):
        pass


class PhaseZeroGuiIpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_unlocked_fluent_window_serves_ciphered_secret_to_cli_child(self):
        sample_value = "phase0-gui-sample-17ac"
        expected_digest = hashlib.sha256(sample_value.encode()).hexdigest()
        child_code = (
            "import hashlib,os,sys; "
            "value=os.environ['PHASE0_GUI_KEY']; "
            "sys.exit(0 if hashlib.sha256(value.encode()).hexdigest()==sys.argv[1] "
            "and value not in sys.argv else 29)"
        )

        with tempfile.TemporaryDirectory(prefix="phase0-gui-") as directory:
            data_dir = Path(directory)
            vault_manager = VaultManager(data_dir)
            vault = vault_manager.create("phase-zero temporary password")
            database = Database(vault_manager.database_path, vault.get_dek())
            database.create_tables()
            service = SecretService(SqliteSecretRepository(
                database.Session,
                vault.get_dek,
            ))
            service.create(name="PHASE0_GUI_KEY", value=sample_value, allow_cli=True)

            with (
                patch.object(main_window_module, "get_data_dir", return_value=data_dir),
                patch.object(main_window_module, "ThemeManager", _ThemeManagerStub),
            ):
                window = main_window_module.MainWindow()

            window.vault_manager = vault_manager
            window.vault = vault
            window.database = database
            window.secret_service = service
            window.secrets_page.set_service(service)
            window._update_vault_ui()
            window._start_ipc_server()
            self.assertIsNotNone(window.ipc_server)

            with patch.object(cli, "get_data_dir", return_value=data_dir):
                result = cli.main([
                    "--use", "PHASE0_GUI_KEY", "--",
                    sys.executable, "-c", child_code, expected_digest,
                ])
            self.assertEqual(result, 0)

            server = window.ipc_server
            window.close()
            self.assertIsNone(window.ipc_server)
            self.assertTrue(server.wait_closed(3))
            self.assertFalse((data_dir / ".ipc-token").exists())
            self.app.processEvents()


    def test_lock_interrupts_active_database_query_and_cancels_cli(self):
        query_started = threading.Event()
        query_errors = []
        request_result = {}
        sample_value = "lifecycle-secret-value"

        with tempfile.TemporaryDirectory(prefix="phase0-lock-ipc-") as directory:
            data_dir = Path(directory)
            vault_manager = VaultManager(data_dir)
            vault = vault_manager.create("temporary password")
            database = Database(vault_manager.database_path, vault.get_dek())
            database.create_tables()
            service = SecretService(SqliteSecretRepository(
                database.Session,
                vault.get_dek,
            ))
            service.create(name="LIFECYCLE_KEY", value=sample_value, allow_cli=True)

            with (
                patch.object(main_window_module, "get_data_dir", return_value=data_dir),
                patch.object(main_window_module, "ThemeManager", _ThemeManagerStub),
            ):
                window = main_window_module.MainWindow()

            window.vault_manager = vault_manager
            window.vault = vault
            window.database = database
            window.secret_service = service
            window.secrets_page.set_service(service)
            window._update_vault_ui()
            window._start_ipc_server()
            server = window.ipc_server
            self.assertIsNotNone(server)

            original_get = service.get

            def interruptible_lookup(name):
                connection = database.engine.raw_connection()
                try:
                    def mark_query_running():
                        query_started.set()
                        return 0

                    connection.set_progress_handler(mark_query_running, 1000)
                    cursor = connection.cursor()
                    try:
                        cursor.execute(
                            "WITH RECURSIVE counter(value) AS ("
                            "VALUES(0) UNION ALL "
                            "SELECT value + 1 FROM counter WHERE value < 100000000"
                            ") SELECT sum(value) FROM counter"
                        )
                        cursor.fetchone()
                    except Exception as error:
                        query_errors.append(error)
                    finally:
                        cursor.close()
                finally:
                    connection.close()
                return original_get(name)

            server.get_secret = interruptible_lookup
            database.close = Mock(wraps=database.close)

            def request():
                try:
                    request_result["grants"] = request_secrets(
                        data_dir,
                        ["LIFECYCLE_KEY"],
                    )
                except Exception as error:
                    request_result["error"] = error

            client_thread = threading.Thread(target=request)
            client_thread.start()
            try:
                self.assertTrue(query_started.wait(3))
                window._lock_vault()
                self.assertFalse(vault.is_unlocked)
                self.assertIsNone(window.database)
                database.close.assert_called_once_with()
                client_thread.join(3)
                self.assertFalse(client_thread.is_alive())
                self.assertIsInstance(
                    request_result.get("error"),
                    IpcRequestCancelledError,
                )
                self.assertNotIn("grants", request_result)
            finally:
                if vault.is_unlocked:
                    window._lock_vault()
                client_thread.join(3)

            self.assertTrue(server.wait_closed(3))
            self.assertTrue(query_errors)
            self.assertIn("interrupt", str(query_errors[0]).lower())
            self.assertFalse(database._active_connections)
            window.close()
            self.app.processEvents()
if __name__ == "__main__":
    unittest.main()
