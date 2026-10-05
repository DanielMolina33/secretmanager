"""Linux session-lock notifications from systemd-logind over Qt D-Bus."""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, SLOT, Signal, Slot
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage


logger = logging.getLogger(__name__)
_SERVICE = "org.freedesktop.login1"
_MANAGER_PATH = "/org/freedesktop/login1"
_MANAGER_INTERFACE = "org.freedesktop.login1.Manager"
_SESSION_INTERFACE = "org.freedesktop.login1.Session"


class LinuxSessionMonitor(QObject):
    lockRequested = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._bus = QDBusConnection.systemBus()
        self._session_path = None
        self._sleep_connected = False
        self._lock_connected = False

    def start(self) -> None:
        if not self._bus.isConnected():
            raise RuntimeError("The system D-Bus is unavailable.")

        self._sleep_connected = self._bus.connect(
            _SERVICE,
            _MANAGER_PATH,
            _MANAGER_INTERFACE,
            "PrepareForSleep",
            self,
            SLOT("on_prepare_for_sleep(bool)"),
        )
        if not self._sleep_connected:
            raise RuntimeError("Could not subscribe to logind sleep notifications.")

        manager = QDBusInterface(
            _SERVICE,
            _MANAGER_PATH,
            _MANAGER_INTERFACE,
            self._bus,
            self,
        )
        reply = manager.call("GetSessionByPID", os.getpid())
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            logger.warning("logind did not return this process's session: %s", reply.errorMessage())
            return

        arguments = reply.arguments()
        if not arguments:
            logger.warning("logind returned no session path for this process.")
            return

        self._session_path = str(arguments[0])
        self._lock_connected = self._bus.connect(
            _SERVICE,
            self._session_path,
            _SESSION_INTERFACE,
            "Lock",
            self,
            SLOT("on_session_lock()"),
        )
        if not self._lock_connected:
            logger.warning("Could not subscribe to this session's logind lock signal.")

    @Slot(bool)
    def on_prepare_for_sleep(self, preparing: bool) -> None:
        if preparing:
            self.lockRequested.emit()

    @Slot()
    def on_session_lock(self) -> None:
        self.lockRequested.emit()

    def close(self) -> None:
        if self._sleep_connected:
            self._bus.disconnect(
                _SERVICE,
                _MANAGER_PATH,
                _MANAGER_INTERFACE,
                "PrepareForSleep",
                self,
                SLOT("on_prepare_for_sleep(bool)"),
            )
            self._sleep_connected = False
        if self._lock_connected and self._session_path is not None:
            self._bus.disconnect(
                _SERVICE,
                self._session_path,
                _SESSION_INTERFACE,
                "Lock",
                self,
                SLOT("on_session_lock()"),
            )
            self._lock_connected = False
