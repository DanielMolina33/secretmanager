from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from secretmanager.database.database import Database
from secretmanager.ipc import request_secrets
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


class _SystemEventMonitorStub(QObject):
    lockRequested = Signal()

    def __init__(self, _window, parent=None):
        super().__init__(parent)

    def close(self):
        pass


class GuiIpcLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_unlocked_window(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "config.json").write_text(
            json.dumps({"SecretManager": {"CliIntegrationEnabled": True}}),
            encoding="utf-8",
        )
        manager = VaultManager(data_dir)
        vault = manager.create("temporary master passphrase")
        database = Database(manager.database_path, vault.get_dek())
        database.create_tables()
        service = SecretService(
            SqliteSecretRepository(database.Session, vault.get_dek)
        )
        service.create("GUI_IPC_SECRET", "gui-ipc-value-52f1", allow_cli=True)

        with (
            patch.object(main_window_module, "get_data_dir", return_value=data_dir),
            patch.object(main_window_module, "ThemeManager", _ThemeManagerStub),
            patch.object(
                main_window_module,
                "SystemEventMonitor",
                _SystemEventMonitorStub,
            ),
        ):
            window = main_window_module.MainWindow()

        window.vault_manager = manager
        window.vault = vault
        window.database = database
        window.secret_service = service
        window._update_vault_ui()
        return window, vault, database, service

    def _wait_for_ipc_ready(self, window):
        window._start_cli_integration()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            self.app.processEvents()
            worker = window.ipc_worker
            if worker is not None and window.ipc_lifecycle_thread is None:
                result = worker.poll_startup()
                if result is True:
                    return worker
                if result is False:
                    self.fail(f"IPC worker startup failed: {worker.failure_reason}")
            time.sleep(0.05)
        self.fail("MainWindow did not start the IPC worker within 30 seconds")

    def test_unlocked_window_starts_cli_worker_and_lock_removes_ipc_access(self):
        with tempfile.TemporaryDirectory(prefix="gui-ipc-lifecycle-") as directory:
            data_dir = Path(directory)
            window, vault, database, _service = self._make_unlocked_window(data_dir)
            try:
                with patch.object(
                    window,
                    "_cli_integration_should_run",
                    return_value=True,
                ):
                    self._wait_for_ipc_ready(window)

                grant = request_secrets(data_dir, ["GUI_IPC_SECRET"])
                self.assertEqual(grant["GUI_IPC_SECRET"].value, "gui-ipc-value-52f1")

                window._lock_vault()

                self.assertFalse(vault.is_unlocked)
                self.assertTrue(database._closed)
                self.assertIsNone(window.database)
                self.assertIsNone(window.secret_service)
                self.assertIsNone(window.ipc_worker)
                self.assertFalse((data_dir / ".ipc-token").exists())
                with self.assertRaises(OSError):
                    request_secrets(data_dir, ["GUI_IPC_SECRET"])


                window.close()
                self.app.processEvents()
            finally:
                if vault.is_unlocked:
                    window._lock_vault()
                window.close()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()




