"""Linux session-lock notifications from systemd-logind over Qt D-Bus."""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess

from PySide6.QtCore import QObject, SLOT, Signal, Slot
from PySide6.QtDBus import QDBusConnection


logger = logging.getLogger(__name__)
_SERVICE = "org.freedesktop.login1"
_MANAGER_PATH = "/org/freedesktop/login1"
_MANAGER_INTERFACE = "org.freedesktop.login1.Manager"
_SESSION_INTERFACE = "org.freedesktop.login1.Session"
_SESSION_PATH_PATTERN = re.compile(r'^o\s+"([^"\r\n]+)"\s*$')


def _session_path_for_pid(pid: int) -> str | None:
    """Resolve this process's logind session, including via its session ID."""
    command = [
        "busctl",
        "--system",
        "call",
        _SERVICE,
        _MANAGER_PATH,
        _MANAGER_INTERFACE,
        "GetSessionByPID",
        "u",
        str(pid),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.CalledProcessError as error:
        # Some launchers place the application outside a logind session cgroup.
        # In that case, use the session ID exported by the desktop environment.
        session_id = os.environ.get("XDG_SESSION_ID")
        if session_id:
            try:
                result = subprocess.run(
                    [
                        "busctl",
                        "--system",
                        "call",
                        _SERVICE,
                        _MANAGER_PATH,
                        _MANAGER_INTERFACE,
                        "GetSession",
                        "s",
                        session_id,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except (OSError, subprocess.SubprocessError) as fallback_error:
                logger.warning(
                    "Could not resolve this process's logind session by PID or "
                    "XDG_SESSION_ID=%r: %s",
                    session_id,
                    _process_error_detail(fallback_error),
                )
                return None
        else:
            logger.info(
                "logind could not map PID %s to a session and XDG_SESSION_ID is "
                "not set; searching for this user's active graphical session: %s",
                pid,
                _process_error_detail(error),
            )
            return _active_graphical_session_path(os.getuid())
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning(
            "Could not query logind for this process's session: %s",
            _process_error_detail(error),
        )
        return None

    match = _SESSION_PATH_PATTERN.fullmatch(result.stdout.strip())
    if match is None:
        logger.warning("logind returned an unexpected session path: %r", result.stdout.strip())
        return None
    return match.group(1)


def _active_graphical_session_path(uid: int) -> str | None:
    """Find this user's unique active graphical session through logind."""
    try:
        result = subprocess.run(
            [
                "busctl",
                "--system",
                "call",
                _SERVICE,
                _MANAGER_PATH,
                _MANAGER_INTERFACE,
                "ListSessions",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        fields = shlex.split(result.stdout)
        if len(fields) < 2 or fields[0] != "a(susso)":
            raise ValueError(f"unexpected ListSessions response: {result.stdout.strip()!r}")
        count = int(fields[1])
        sessions = fields[2:]
        if len(sessions) != count * 5:
            raise ValueError(f"unexpected ListSessions response: {result.stdout.strip()!r}")

        candidates = []
        for offset in range(0, len(sessions), 5):
            session_id, session_uid, _name, seat_id, object_path = sessions[offset : offset + 5]
            if int(session_uid) != uid or not seat_id:
                continue
            active = _session_property(object_path, "Active")
            session_type = _session_property(object_path, "Type")
            if active == "true" and session_type in {"x11", "wayland"}:
                candidates.append((session_id, object_path))

        if len(candidates) == 1:
            session_id, object_path = candidates[0]
            logger.info(
                "Using the unique active graphical logind session %s for this user.",
                session_id,
            )
            return object_path
        if len(candidates) > 1:
            logger.warning(
                "Could not choose a logind session: this user has multiple active "
                "graphical sessions."
            )
        else:
            logger.warning(
                "Could not find an active graphical logind session for this user."
            )
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        logger.warning(
            "Could not find this user's active graphical logind session: %s",
            _process_error_detail(error),
        )
    return None


def _session_property(object_path: str, property_name: str) -> str:
    result = subprocess.run(
        [
            "busctl",
            "--system",
            "get-property",
            _SERVICE,
            object_path,
            _SESSION_INTERFACE,
            property_name,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    values = shlex.split(result.stdout)
    if len(values) != 2:
        raise ValueError(f"unexpected logind property response: {result.stdout.strip()!r}")
    return values[1]


def _process_error_detail(error: BaseException) -> str:
    """Include stderr from busctl so logind failures are diagnosable."""
    stderr = getattr(error, "stderr", None)
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    if stderr:
        return str(stderr).strip()
    return str(error)


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

        self._session_path = _session_path_for_pid(os.getpid())
        if self._session_path is None:
            return

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
