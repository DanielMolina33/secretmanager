"""Process boundary for the optional local CLI IPC service.

The server and database dependencies are imported only in the worker process.
Stopping the worker releases that feature runtime.
"""

from __future__ import annotations

import multiprocessing
import os
import stat
import time
from multiprocessing.connection import Connection
from pathlib import Path


class IpcWorkerProcess:
    """Own the optional IPC runtime outside the GUI process."""

    def __init__(self, data_dir: Path, database_path: Path, key: bytes):
        self.data_dir = Path(data_dir)
        self.database_path = Path(database_path)
        self._key = bytes(key)
        self._context = multiprocessing.get_context("spawn")
        self._connection: Connection | None = None
        self._process = None
        self._started_at = 0.0
        self._ready = False
        self._endpoint_owned = False
        self.failure_reason: str | None = None
        self._stop_requested = False

    def start(self) -> None:
        parent_connection, child_connection = self._context.Pipe(duplex=True)
        process = self._context.Process(
            target=_run_ipc_worker,
            args=(child_connection, str(self.data_dir), str(self.database_path)),
            name="secretmanager-cli-ipc",
            daemon=True,
        )
        try:
            process.start()
        except Exception:
            parent_connection.close()
            child_connection.close()
            raise

        child_connection.close()
        self._connection = parent_connection
        self._process = process
        self._started_at = time.monotonic()
        try:
            parent_connection.send_bytes(self._key)
        finally:
            self._key = b""

    def poll_startup(self) -> bool | None:
        """Return True when ready, False after failure, or None while starting."""
        process = self._process
        connection = self._connection
        if process is None or connection is None:
            return False
        if self._ready:
            if process.is_alive():
                return True
            self.failure_reason = "worker process exited after startup"
            return False

        if connection.poll():
            try:
                response = connection.recv_bytes(256).decode("ascii", errors="replace")
            except (EOFError, OSError):
                response = "worker exited before becoming ready"
            if response == "ready":
                self._ready = True
                self._endpoint_owned = True
                return True
            self.failure_reason = response.removeprefix("error:")
            return False

        if not process.is_alive():
            self.failure_reason = "worker process exited during startup"
            return False
        if time.monotonic() - self._started_at > 30:
            self.failure_reason = "worker startup timed out"
            return False
        return None

    def request_stop(self) -> None:
        """Ask the worker to stop without waiting for process cleanup."""
        if self._stop_requested:
            return
        self._stop_requested = True

        process = self._process
        connection = self._connection
        if connection is not None and process is not None and process.is_alive():
            try:
                connection.send_bytes(b"stop")
            except (EOFError, OSError):
                pass

    def stop(self) -> None:
        self.request_stop()
        process = self._process
        self._process = None
        connection = self._connection
        self._connection = None

        if process is not None:
            if process.is_alive():
                process.join(timeout=1)
            if process.is_alive():
                try:
                    process.terminate()
                except OSError:
                    pass
                process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join()
            else:
                process.join()
            try:
                process.close()
            except ValueError:
                pass

        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

        if self._endpoint_owned:
            self._remove_owned_endpoint_files()
            self._endpoint_owned = False

    def _remove_owned_endpoint_files(self) -> None:
        try:
            (self.data_dir / ".ipc-token").unlink()
        except OSError:
            pass

        if os.name == "nt":
            return

        socket_path = self.data_dir / "secretmanager.sock"
        try:
            if stat.S_ISSOCK(socket_path.lstat().st_mode):
                socket_path.unlink()
        except OSError:
            pass


def _run_ipc_worker(
    control: Connection,
    data_dir_text: str,
    database_path_text: str,
) -> None:
    """Open the encrypted vault and serve CLI requests in this process only."""
    database = None
    server = None
    startup_reported = False
    server_started = False
    try:
        key = control.recv_bytes(1024)
        if not key:
            raise ValueError("missing database key")

        # Keep all feature and database imports inside the child process.
        from .database.database import Database
        from .repositories.sqlite_secret_repository import SqliteSecretRepository
        from .services.secret_service import SecretService
        from .ipc import LocalSecretServer

        database = Database(Path(database_path_text), key)
        del key
        repository = SqliteSecretRepository(database.Session, lambda: database.key)
        service = SecretService(repository)
        server = LocalSecretServer(Path(data_dir_text), service.get)
        server.start()
        server_started = True
        control.send_bytes(b"ready")
        startup_reported = True

        while True:
            if not control.poll(0.2):
                continue
            try:
                command = control.recv_bytes(32)
            except EOFError:
                break
            if command == b"stop":
                break
    except Exception as error:
        if not startup_reported:
            try:
                control.send_bytes(f"error:{type(error).__name__}".encode("ascii"))
            except (EOFError, OSError):
                pass
    finally:
        try:
            if server is not None and server_started:
                server.close()
        finally:
            try:
                if database is not None:
                    database.close()
            finally:
                if server is not None and server_started:
                    server.wait_closed(timeout=2)
                try:
                    control.close()
                except OSError:
                    pass
