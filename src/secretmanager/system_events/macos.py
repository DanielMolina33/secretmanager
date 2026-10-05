"""macOS session notifications through NSWorkspace's documented API."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Foundation import NSOperationQueue


class MacOSSessionMonitor(QObject):
    lockRequested = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        from AppKit import (
            NSWorkspace,
            NSWorkspaceSessionDidResignActiveNotification,
        )

        self._notification_center = NSWorkspace.sharedWorkspace().notificationCenter()
        self._main_queue = NSOperationQueue.mainQueue()
        self._observer = self._notification_center.addObserverForName_object_queue_usingBlock_(
            NSWorkspaceSessionDidResignActiveNotification,
            None,
            self._main_queue,
            self._on_session_resigned_active,
        )

    def _on_session_resigned_active(self, _notification) -> None:
        self.lockRequested.emit()

    def start(self) -> None:
        return None

    def close(self) -> None:
        observer, self._observer = self._observer, None
        if observer is not None:
            self._notification_center.removeObserver_(observer)
