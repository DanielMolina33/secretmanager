"""Single-instance lock and window-activation channel."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QAbstractSocket, QLocalServer, QLocalSocket

from .platforms import get_backend


_ACTIVATE_MESSAGE = bytes([1])


class InstanceCoordinator(QObject):
    """Own the global per-user lock and accept activation requests."""

    activated = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._backend, self.server_name = get_backend()
        self._lock = self._backend.create_lock()
        self._server: QLocalServer | None = None
        self._owns_lock = False

    def start(self) -> bool:
        """Return True for the primary process; False if another owns the lock."""
        if not self._lock.acquire():
            return False
        self._owns_lock = True

        server = QLocalServer(self)
        self._backend.configure_server(server)
        server.newConnection.connect(self._accept_connections)
        if not server.listen(self.server_name):
            stale_endpoint = (
                self._backend.recover_stale_server
                and server.serverError() == QAbstractSocket.SocketError.AddressInUseError
                and not self._server_is_reachable()
            )
            if stale_endpoint:
                QLocalServer.removeServer(self.server_name)
                if server.listen(self.server_name):
                    self._server = server
                    return True
            message = server.errorString()
            self.close()
            raise RuntimeError(f"Could not start the activation endpoint: {message}")

        self._server = server
        return True

    def _server_is_reachable(self) -> bool:
        probe = QLocalSocket()
        self._backend.configure_client(probe)
        probe.connectToServer(self.server_name)
        reachable = probe.waitForConnected(100)
        probe.abort()
        return reachable

    def request_activation(self) -> bool:
        """Ask the primary process to show and activate its window."""
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            client = QLocalSocket()
            self._backend.configure_client(client)
            client.connectToServer(self.server_name)
            if client.waitForConnected(100):
                client.write(_ACTIVATE_MESSAGE)
                client.flush()
                client.waitForBytesWritten(500)
                client.disconnectFromServer()
                return True
            client.abort()
            time.sleep(0.04)
        return False

    def _accept_connections(self) -> None:
        server = self._server
        if server is None:
            return
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                continue
            connection.readyRead.connect(
                lambda connection=connection: self._read_activation(connection)
            )
            connection.disconnected.connect(connection.deleteLater)
            if connection.bytesAvailable():
                self._read_activation(connection)

    def _read_activation(self, connection: QLocalSocket) -> None:
        message = bytes(connection.readAll())
        if message == _ACTIVATE_MESSAGE:
            self.activated.emit()
        connection.disconnectFromServer()

    def close(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.close()
        if self._owns_lock:
            self._owns_lock = False
            self._lock.release()
