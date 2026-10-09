from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secretmanager.database.database import Database
from secretmanager.ipc import CliPermissionDeniedError, request_secrets
from secretmanager.ipc_process import IpcWorkerProcess
from secretmanager.repositories.sqlite_secret_repository import SqliteSecretRepository
from secretmanager.services.secret_service import SecretService


class IpcWorkerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="ipc-worker-lifecycle-")
        self.data_dir = Path(self.temp_dir.name)
        self.key = b"i" * 32
        self.database_path = self.data_dir / "vault.db"
        self.database = Database(self.database_path, self.key)
        self.database.create_tables()
        service = SecretService(
            SqliteSecretRepository(self.database.Session, lambda: self.key)
        )
        self.expected_value = "ipc-worker-cross-platform-secret"
        service.create("WORKER_ALLOWED", self.expected_value, allow_cli=True)
        service.create("WORKER_DENIED", "must-not-be-granted")
        self.workers: list[IpcWorkerProcess] = []

    def tearDown(self):
        for worker in reversed(self.workers):
            worker.stop()
        self.database.close()
        self.temp_dir.cleanup()

    def _start_worker(self) -> IpcWorkerProcess:
        worker = IpcWorkerProcess(self.data_dir, self.database_path, self.key)
        self.workers.append(worker)
        worker.start()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = worker.poll_startup()
            if result is True:
                return worker
            if result is False:
                self.fail(f"IPC worker failed to start: {worker.failure_reason}")
            time.sleep(0.05)
        worker.stop()
        self.fail("IPC worker did not report ready within 30 seconds")

    def test_spawned_worker_serves_allowed_secret_and_stops_cleanly(self):
        worker = self._start_worker()
        grants = request_secrets(self.data_dir, ["WORKER_ALLOWED"])
        self.assertEqual(grants["WORKER_ALLOWED"].value, self.expected_value)

        worker.stop()
        self.assertFalse((self.data_dir / ".ipc-token").exists())
        self.assertFalse((self.data_dir / "secretmanager.sock").exists())
        with self.assertRaises(OSError):
            request_secrets(self.data_dir, ["WORKER_ALLOWED"])

    def test_worker_can_restart_and_permission_denial_does_not_return_grants(self):
        self._start_worker()
        worker = self.workers[-1]
        worker.stop()
        restarted = self._start_worker()

        self.assertEqual(
            request_secrets(self.data_dir, ["WORKER_ALLOWED"])["WORKER_ALLOWED"].value,
            self.expected_value,
        )
        with self.assertRaises(CliPermissionDeniedError):
            request_secrets(self.data_dir, ["WORKER_ALLOWED", "WORKER_DENIED"])

        restarted.stop()
        self.assertFalse((self.data_dir / ".ipc-token").exists())


if __name__ == "__main__":
    unittest.main()

