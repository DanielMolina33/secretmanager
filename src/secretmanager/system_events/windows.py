"""Windows session-lock notifications through documented WTS APIs."""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QObject, QAbstractNativeEventFilter, Signal
from PySide6.QtWidgets import QApplication


logger = logging.getLogger(__name__)

_WM_WTSSESSION_CHANGE = 0x02B1
_WTS_SESSION_LOCK = 0x7
_NOTIFY_FOR_THIS_SESSION = 0


class _Point(ctypes.Structure):
    _fields_ = (("x", wintypes.LONG), ("y", wintypes.LONG))


class _Message(ctypes.Structure):
    _fields_ = (
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _Point),
    )


class _WtsEventFilter(QAbstractNativeEventFilter):
    def __init__(self, on_session_lock):
        super().__init__()
        self._on_session_lock = on_session_lock

    def nativeEventFilter(self, event_type, message):
        event_name = (
            event_type.encode()
            if isinstance(event_type, str)
            else bytes(event_type)
        )
        if event_name not in (
            b"windows_generic_MSG",
            b"windows_dispatcher_MSG",
        ):
            return False, 0

        try:
            address = int(message)
            native_message = ctypes.cast(
                address,
                ctypes.POINTER(_Message),
            ).contents
        except (TypeError, ValueError, OSError):
            return False, 0

        if (
            native_message.message == _WM_WTSSESSION_CHANGE
            and native_message.wParam == _WTS_SESSION_LOCK
        ):
            self._on_session_lock()

        return False, 0


class WindowsSessionMonitor(QObject):
    lockRequested = Signal()

    def __init__(self, window, parent: QObject | None = None):
        super().__init__(parent)
        self._window = window
        self._application = QApplication.instance()
        self._filter = _WtsEventFilter(self.lockRequested.emit)
        self._wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
        self._wtsapi32.WTSRegisterSessionNotification.argtypes = (
            wintypes.HWND,
            wintypes.DWORD,
        )
        self._wtsapi32.WTSRegisterSessionNotification.restype = wintypes.BOOL
        self._wtsapi32.WTSUnRegisterSessionNotification.argtypes = (wintypes.HWND,)
        self._wtsapi32.WTSUnRegisterSessionNotification.restype = wintypes.BOOL
        self._window_handle = None

    def start(self) -> None:
        if self._application is None:
            return

        self._application.installNativeEventFilter(self._filter)
        self._window_handle = wintypes.HWND(int(self._window.winId()))
        if not self._wtsapi32.WTSRegisterSessionNotification(
            self._window_handle,
            _NOTIFY_FOR_THIS_SESSION,
        ):
            error = ctypes.get_last_error()
            self._application.removeNativeEventFilter(self._filter)
            self._window_handle = None
            raise OSError(error, "WTSRegisterSessionNotification failed")

    def close(self) -> None:
        if self._application is not None:
            self._application.removeNativeEventFilter(self._filter)
        if self._window_handle is not None:
            self._wtsapi32.WTSUnRegisterSessionNotification(self._window_handle)
            self._window_handle = None
