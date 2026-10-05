"""Windows named-mutex implementation using documented Win32 APIs."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field

from PySide6.QtNetwork import QLocalServer, QLocalSocket


_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080
_WAIT_TIMEOUT = 0x00000102


@dataclass
class WindowsMutexLock:
    name: str
    _handle: int | None = None
    _owns_mutex: bool = False
    _kernel32: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateMutexW.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        self._kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self._kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        self._kernel32.ReleaseMutex.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel32.CloseHandle.restype = wintypes.BOOL

    def acquire(self) -> bool:
        handle = self._kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            error = ctypes.get_last_error()
            raise OSError(error, "CreateMutexW failed")

        result = self._kernel32.WaitForSingleObject(handle, 0)
        if result in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
            self._handle = handle
            self._owns_mutex = True
            return True

        self._kernel32.CloseHandle(handle)
        if result == _WAIT_TIMEOUT:
            return False
        error = ctypes.get_last_error()
        raise OSError(error, "WaitForSingleObject failed")

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        if self._owns_mutex:
            self._kernel32.ReleaseMutex(handle)
            self._owns_mutex = False
        self._kernel32.CloseHandle(handle)


def create_backend(scope: str):
    mutex_name = rf"Local\SecretManager.Singleton.{scope}"
    server_name = f"secretmanager-single-instance-{scope}"

    def create_lock():
        return WindowsMutexLock(mutex_name)

    def configure_server(server: QLocalServer) -> None:
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)

    def configure_client(_client: QLocalSocket) -> None:
        return None

    from . import PlatformBackend

    return PlatformBackend(create_lock, configure_server, configure_client, False), server_name
