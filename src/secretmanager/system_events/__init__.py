"""System state notifications used to lock the vault."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication


logger = logging.getLogger(__name__)


def _create_session_monitor(parent: QObject, window):
    if sys.platform == "win32":
        from .windows import WindowsSessionMonitor

        return WindowsSessionMonitor(window, parent)
    if sys.platform == "darwin":
        from .macos import MacOSSessionMonitor

        return MacOSSessionMonitor(parent)
    if sys.platform.startswith("linux"):
        from .linux import LinuxSessionMonitor

        return LinuxSessionMonitor(parent)
    return None


class SystemEventMonitor(QObject):
    """Normalize Qt suspend and native session-lock events into one signal."""

    lockRequested = Signal()

    def __init__(self, window, parent: QObject | None = None):
        super().__init__(parent)
        self._application = QApplication.instance()
        self._session_monitor = None
        self._closed = False

        if self._application is not None:
            self._application.applicationStateChanged.connect(
                self._on_application_state_changed
            )

        try:
            self._session_monitor = _create_session_monitor(self, window)
            if self._session_monitor is not None:
                self._session_monitor.lockRequested.connect(self.lockRequested)
                self._session_monitor.start()
        except Exception:
            # Failure to monitor a platform event must not prevent opening the
            # GUI. Qt's suspend notification remains active where supported.
            logger.exception("Could not start the native session-lock monitor.")
            if self._session_monitor is not None:
                try:
                    self._session_monitor.close()
                except Exception:
                    logger.exception("Could not clean up the native session-lock monitor.")
                finally:
                    self._session_monitor.deleteLater()
                self._session_monitor = None

    def _on_application_state_changed(self, state) -> None:
        if state == Qt.ApplicationState.ApplicationSuspended:
            self.lockRequested.emit()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        if self._application is not None:
            try:
                self._application.applicationStateChanged.disconnect(
                    self._on_application_state_changed
                )
            except (RuntimeError, TypeError):
                pass

        if self._session_monitor is not None:
            try:
                self._session_monitor.close()
            except Exception:
                logger.exception("Could not clean up the native session-lock monitor.")
            finally:
                self._session_monitor.deleteLater()
            self._session_monitor = None
