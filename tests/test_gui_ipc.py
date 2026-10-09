from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication
from secretmanager.database.database import Database
from secretmanager.ipc import request_secrets
from secretmanager.repositories.sqlite_secret_repository import SqliteSecretRepository
from secretmanager.services.secret_service import SecretService
from secretmanager.ui import main_window as main_window_module
from secretmanager.vault_manager import VaultManager


class _SecretsPageStub:
    def cancel_pending_page_load(self):
        pass

    def reject_active_secret_dialog(self):
        pass

    def set_service(self, _service):
        pass


class _MainWindowLifecycleHarness(QObject):
    """Run MainWindow's IPC hooks without creating its native frameless window."""

    _start_cli_integration = main_window_module.MainWindow._start_cli_integration
    _start_ipc_lifecycle_operation = (
        main_window_module.MainWindow._start_ipc_lifecycle_operation
    )
    _ipc_lifecycle_finished = main_window_module.MainWindow._ipc_lifecycle_finished
    _check_ipc_worker = main_window_module.MainWindow._check_ipc_worker
    _stop_cli_integration = main_window_module.MainWindow._stop_cli_integration
    _lock_vault = main_window_module.MainWindow._lock_vault

    def __init__(self, vault_manager, vault, database, secret_service):
        super().__init__()
        self.vault_manager = vault_manager
        self.vault = vault
        self.database = database
        self.secret_service = secret_service
        self.secrets_page = _SecretsPageStub()
        self.auto_lock_timer = QTimer(self)
        self.ipc_monitor_timer = QTimer(self)
        self.ipc_monitor_timer.setInterval(1000)
        self.ipc_monitor_timer.timeout.connect(self._check_ipc_worker)
        self.ipc_worker = None
        self.ipc_lifecycle_thread = None
        self._ipc_stop_after_start = False

    def _cli_integration_should_run(self):
        return bool(
            self.vault is not None
            and self.vault.is_unlocked
            and self.secret_service is not None
        )

    def _update_vault_ui(self):
        pass


class GuiIpcLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_unlocked_lifecycle(self, data_dir: Path):
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
        service.create("GUI_IPC_SECRET", "test-only-gui-ipc-secret", allow_cli=True)
        lifecycle = _MainWindowLifecycleHarness(manager, vault, database, service)
        return lifecycle, vault, database

    def _wait_for_ipc_ready(self, lifecycle):
        lifecycle._start_cli_integration()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            self.app.processEvents()
            worker = lifecycle.ipc_worker
            if worker is not None and lifecycle.ipc_lifecycle_thread is None:
                result = worker.poll_startup()
                if result is True:
                    return worker
                if result is False:
                    self.fail(f"IPC worker startup failed: {worker.failure_reason}")
            time.sleep(0.05)
        self.fail("MainWindow IPC lifecycle did not start the worker within 30 seconds")

    def test_unlock_lock_lifecycle_starts_worker_and_removes_ipc_access(self):
        with tempfile.TemporaryDirectory(prefix="sm-") as directory:
            data_dir = Path(directory)
            lifecycle, vault, database = self._make_unlocked_lifecycle(data_dir)
            try:
                self._wait_for_ipc_ready(lifecycle)

                grant = request_secrets(data_dir, ["GUI_IPC_SECRET"])
                self.assertEqual(grant["GUI_IPC_SECRET"].value, "test-only-gui-ipc-secret")

                lifecycle._lock_vault()

                self.assertFalse(vault.is_unlocked)
                self.assertTrue(database._closed)
                self.assertIsNone(lifecycle.database)
                self.assertIsNone(lifecycle.secret_service)
                self.assertIsNone(lifecycle.ipc_worker)
                self.assertFalse((data_dir / ".ipc-token").exists())
                with self.assertRaises(OSError):
                    request_secrets(data_dir, ["GUI_IPC_SECRET"])
            finally:
                if vault.is_unlocked:
                    lifecycle._lock_vault()
                self.app.processEvents()
                lifecycle.deleteLater()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
