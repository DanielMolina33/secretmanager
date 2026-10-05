"""macOS singleton backend using Qt shared memory and a local socket."""

from __future__ import annotations

from PySide6.QtNetwork import QLocalServer, QLocalSocket

from ..posix_lock import PosixSharedMemoryLock
from . import PlatformBackend


def create_backend(scope: str):
    lock_key = f"SecretManager.Singleton.v1.{scope}"
    server_name = f"secretmanager-single-instance-{scope}"

    def create_lock():
        return PosixSharedMemoryLock(lock_key)

    def configure_server(_server: QLocalServer) -> None:
        # macOS local sockets use Qt's platform-selected temporary endpoint.
        return None

    def configure_client(_client: QLocalSocket) -> None:
        return None

    return PlatformBackend(create_lock, configure_server, configure_client, True), server_name
