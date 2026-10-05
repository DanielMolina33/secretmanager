# SecretManager

## Single application instance

The desktop application allows one running instance per user session on Windows and per user account on macOS and Linux. Starting it again sends a local activation request to the existing window and exits without a dialog. The coordination key is independent of the portable data directory, so launching another copy from removable storage follows the same rule.

The lock contains no vault data or secret values. Windows uses a named Win32 mutex. Linux and macOS use a Qt shared-memory segment; on Unix, a later launch checks its recorded process ID and recovers a segment left by a crashed process. Window activation uses Qt local IPC: a named pipe on Windows, an abstract local socket on Linux, and a Qt-managed local socket endpoint on macOS. The activation message only asks the open window to show and activate itself.

macOS uses the platform-selected runtime path for its local socket. Qt exposes the active endpoint at runtime through QLocalServer.fullServerName(); the socket is temporary coordination state and contains no vault data.

The lock and activation APIs are documented by [Qt QSharedMemory](https://doc.qt.io/qt-6/qsharedmemory.html), [Qt QLocalServer](https://doc.qt.io/qt-6/qlocalserver.html), [Qt QLocalSocket](https://doc.qt.io/qt-6/qlocalsocket.html), and Microsoft's [CreateMutex](https://learn.microsoft.com/windows/win32/api/synchapi/nf-synchapi-createmutexw) and [WaitForSingleObject](https://learn.microsoft.com/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject) APIs.
