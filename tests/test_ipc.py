from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from multiprocessing.connection import AuthenticationError, Client
from secretmanager import cli
from secretmanager.database.database import Database
from secretmanager.ipc import LocalSecretServer, _endpoint
from secretmanager.repositories.sqlite_secret_repository import SqliteSecretRepository
from secretmanager.services.secret_service import SecretService


class PhaseZeroIpcTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        (self.data_dir / "config.json").write_text(
            json.dumps({"SecretManager": {"CliIntegrationEnabled": True}}),
            encoding="utf-8",
        )
        self.sample_value = "phase0-sample-9f43c1"
        self.encryption_key = b"k" * 32
        self.database = Database(
            self.data_dir / "vault.db",
            self.encryption_key,
        )
        self.database.create_tables()
        repository = SqliteSecretRepository(
            self.database.Session,
            lambda: self.encryption_key,
        )
        self.secret_service = SecretService(repository)
        self.secret_service.create(
            name="PHASE0_KEY",
            value=self.sample_value,
            allow_cli=True,
        )
        self.server = LocalSecretServer(
            self.data_dir,
            self.secret_service.get,
        )
        self.server.start()

    def tearDown(self):
        self.server.close()
        self.database.close()
        self.temp_dir.cleanup()

    def test_cli_injects_secret_only_into_child_environment(self):
        expected_digest = hashlib.sha256(self.sample_value.encode()).hexdigest()
        child_code = (
            "import hashlib,os,sys; "
            "value=os.environ['PHASE0_KEY']; "
            "sys.exit(0 if hashlib.sha256(value.encode()).hexdigest()==sys.argv[1] "
            "and value not in sys.argv else 19)"
        )
        command = [sys.executable, "-c", child_code, expected_digest]
        with patch.object(cli, "get_data_dir", return_value=self.data_dir):
            result = cli.main([
                "--use", "PHASE0_KEY", "--", *command,
            ])
        self.assertEqual(result, 0)

    def test_child_exit_code_is_returned(self):
        with patch.object(cli, "get_data_dir", return_value=self.data_dir):
            result = cli.main([
                "--use", "PHASE0_KEY", "--",
                sys.executable, "-c", "raise SystemExit(23)",
            ])
        self.assertEqual(result, 23)

    def test_transport_is_local_and_never_tcp(self):
        expected_family = "AF_PIPE" if os.name == "nt" else "AF_UNIX"
        self.assertEqual(self.server.family, expected_family)

    def test_untrusted_client_without_token_is_rejected(self):
        address, family = _endpoint(self.data_dir)
        client_code = (
            "import sys\n"
            "from multiprocessing.connection import AuthenticationError, Client\n"
            "try:\n"
            "    Client(sys.argv[1], family=sys.argv[2], authkey=b'x' * 32)\n"
            "except AuthenticationError:\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(1)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", client_code, address, family],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
    def test_no_secret_value_is_written_to_data_directory(self):
        expected_names = {".ipc-token", "vault.db", "config.json"}
        if self.server.family == "AF_UNIX":
            expected_names.add("secretmanager.sock")
        self.assertEqual({path.name for path in self.data_dir.iterdir()}, expected_names)
        token_path = self.data_dir / ".ipc-token"
        self.assertNotEqual(token_path.read_bytes(), self.sample_value.encode())
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_attributes = kernel32.GetFileAttributesW
            get_attributes.argtypes = (wintypes.LPCWSTR,)
            get_attributes.restype = wintypes.DWORD
            attributes = get_attributes(str(token_path))
            self.assertNotEqual(attributes, 0xFFFFFFFF)
            self.assertTrue(attributes & 0x02)

    def test_start_failure_removes_token_and_owned_endpoint(self):
        failed_dir = self.data_dir / "failed-start"
        failed_dir.mkdir()
        server = LocalSecretServer(failed_dir, self.secret_service.get)
        write_token = server._write_token

        def write_then_fail():
            write_token()
            raise RuntimeError("injected startup failure")

        with patch.object(server, "_write_token", side_effect=write_then_fail):
            with self.assertRaisesRegex(RuntimeError, "injected startup failure"):
                server.start()

        self.assertFalse((failed_dir / ".ipc-token").exists())
        if server.family == "AF_UNIX":
            self.assertFalse((failed_dir / "secretmanager.sock").exists())

    def test_cli_module_does_not_import_qt(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        check = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, secretmanager.cli; "
                "assert 'PySide6' not in sys.modules; "
                "assert 'qfluentwidgets' not in sys.modules",
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stderr)


if __name__ == "__main__":
    unittest.main()
