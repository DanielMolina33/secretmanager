"""Linux singleton backend with a filesystem-independent local endpoint."""

from __future__ import annotations

from PySide6.QtNetwork import QLocalServer, QLocalSocket

from ..posix_lock import PosixSharedMemoryLock
from . import PlatformBackend


def create_backend(scope: str):
    lock_key = f"SecretManager.Singleton.v1.{scope}"
    server_name = f"secretmanager-single-instance-{scope}"

    def create_lock():
        return PosixSharedMemoryLock(lock_key)

    def configure_server(server: QLocalServer) -> None:
        server.setSocketOptions(QLocalServer.SocketOption.AbstractNamespaceOption)

    def configure_client(client: QLocalSocket) -> None:
        client.setSocketOptions(QLocalSocket.SocketOption.AbstractNamespaceOption)

    return PlatformBackend(create_lock, configure_server, configure_client, False), server_name
