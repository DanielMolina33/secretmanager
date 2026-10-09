"""Authenticated, local-only IPC between the GUI vault and CLI."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import stat
import sys
import threading
from dataclasses import dataclass
from multiprocessing.connection import (
    AuthenticationError,
    Client,
    Listener,
)
from pathlib import Path
from typing import Callable

from .domain.expiry import EXPIRED, EXPIRING, VALID, get_expiry_status


TOKEN_FILENAME = ".ipc-token"
SOCKET_FILENAME = "secretmanager.sock"
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_SECRET_NAMES = 128


def _mark_token_hidden_on_windows(path: Path) -> None:
    """Best-effort Windows hidden attribute for the local IPC token."""
    if sys.platform != "win32":
        return

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_attributes = kernel32.GetFileAttributesW
        get_attributes.argtypes = (wintypes.LPCWSTR,)
        get_attributes.restype = wintypes.DWORD
        set_attributes = kernel32.SetFileAttributesW
        set_attributes.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
        set_attributes.restype = wintypes.BOOL

        attributes = get_attributes(str(path))
        if attributes == 0xFFFFFFFF:
            return

        # Keep existing attributes while replacing FILE_ATTRIBUTE_NORMAL.
        attributes = (attributes & ~0x80) | 0x02
        set_attributes(str(path), attributes)
    except (AttributeError, OSError):
        # Hiding is cosmetic and must not prevent CLI IPC from starting.
        pass


@dataclass(frozen=True)
class SecretGrant:
    value: str
    status: str


class CliPermissionDeniedError(RuntimeError):
    """The vault denied CLI use for one or more requested secrets."""


class IpcRequestCancelledError(RuntimeError):
    """The vault stopped serving a CLI request before it completed."""


def _endpoint(data_dir: Path) -> tuple[str, str]:
    if sys.platform == "win32":
        identity = str(data_dir.resolve()).casefold().encode("utf-8")
        suffix = hashlib.sha256(identity).hexdigest()[:24]
        return rf"\\.\pipe\secretmanager-{suffix}", "AF_PIPE"

    path = data_dir / SOCKET_FILENAME
    if len(os.fsencode(path)) >= 100:
        raise OSError("The portable path is too long for a local Unix socket.")
    return str(path), "AF_UNIX"


def request_secrets(data_dir: Path, names: list[str]) -> dict[str, SecretGrant]:
    token_path = data_dir / TOKEN_FILENAME
    token = token_path.read_bytes()
    if len(token) != 32:
        raise ValueError("The local IPC session token is invalid.")

    address, family = _endpoint(data_dir)
    try:
        with Client(address, family=family, authkey=token) as connection:
            connection.send_bytes(json.dumps(
                {"operation": "get", "names": names},
                separators=(",", ":"),
            ).encode("utf-8"))
            response_bytes = connection.recv_bytes(MAX_RESPONSE_BYTES)
    except (AuthenticationError, EOFError, OSError) as error:
        raise IpcRequestCancelledError(
            "The vault was locked or closed before the CLI request completed."
        ) from error

    response = json.loads(response_bytes.decode("utf-8"))

    if not isinstance(response, dict):
        raise RuntimeError("The vault returned an invalid local IPC response.")
    if response.get("error") == "cli_not_allowed":
        denied_names = response.get("names", [])
        if (
            not isinstance(denied_names, list)
            or any(not isinstance(name, str) for name in denied_names)
        ):
            raise RuntimeError("The vault returned an invalid local IPC response.")
        raise CliPermissionDeniedError(", ".join(denied_names))
    if response.get("error") == "secret_not_found":
        missing_names = response.get("names", [])
        if (
            not isinstance(missing_names, list)
            or any(not isinstance(name, str) for name in missing_names)
        ):
            raise RuntimeError("The vault returned an invalid local IPC response.")
        raise KeyError(", ".join(missing_names))
    if not response.get("ok"):
        raise RuntimeError("The vault rejected the local CLI request.")

    secrets_by_name = response.get("secrets")
    if not isinstance(secrets_by_name, dict):
        raise RuntimeError("The vault returned an invalid local IPC response.")
    if set(secrets_by_name) != set(names):
        raise RuntimeError("The vault returned an incomplete local IPC response.")

    grants: dict[str, SecretGrant] = {}
    allowed_statuses = {VALID, EXPIRING, EXPIRED}
    for name, secret_data in secrets_by_name.items():
        if not isinstance(secret_data, dict):
            raise RuntimeError("The vault returned an invalid local IPC response.")
        value = secret_data.get("value")
        status = secret_data.get("status")
        if (
            not isinstance(value, str)
            or not isinstance(status, str)
            or status not in allowed_statuses
        ):
            raise RuntimeError("The vault returned an invalid local IPC response.")
        grants[name] = SecretGrant(value=value, status=status)
    return grants


class LocalSecretServer:
    """Serves secret values to authenticated local CLI clients."""

    def __init__(self, data_dir: Path, get_secret: Callable[[str], object | None]):
        self.data_dir = data_dir
        self.get_secret = get_secret
        self.token_path = data_dir / TOKEN_FILENAME
        self.token = secrets.token_bytes(32)
        self.address, self.family = _endpoint(data_dir)
        self._listener = None
        self._thread = None
        self._stopping = threading.Event()
        self._state_lock = threading.Lock()
        self._connections: set[object] = set()
        self._workers: set[threading.Thread] = set()
        self._closing_started = False
        self._transport_closed = False
        self._closed_event = threading.Event()

    def start(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.family == "AF_UNIX":
            self._remove_stale_socket()

        listener = Listener(
            self.address,
            family=self.family,
            authkey=self.token,
        )
        self._listener = listener
        try:
            if self.family == "AF_UNIX":
                Path(self.address).chmod(0o600)
            self._write_token()
            self._thread = threading.Thread(
                target=self._serve,
                name="secretmanager-local-ipc-listener",
                daemon=True,
            )
            self._thread.start()
        except Exception:
            self._stopping.set()
            self._listener = None
            try:
                listener.close()
            except OSError:
                pass
            thread = self._thread
            if thread is not None and thread.is_alive():
                thread.join()
            try:
                self._remove_endpoint_files()
            except OSError:
                pass
            raise

    def _write_token(self) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        descriptor = os.open(self.token_path, flags, 0o600)
        try:
            if os.name == "posix":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=False) as token_file:
                token_file.write(self.token)
                token_file.flush()
                os.fsync(descriptor)
        finally:
            os.close(descriptor)

        _mark_token_hidden_on_windows(self.token_path)

    def _remove_stale_socket(self) -> None:
        path = Path(self.address)
        if not path.exists():
            return
        if not stat.S_ISSOCK(path.stat().st_mode):
            raise OSError("The local IPC endpoint path is not a socket.")

        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.connect(self.address)
        except (ConnectionRefusedError, FileNotFoundError):
            path.unlink()
        else:
            raise OSError("The local IPC endpoint is already in use.")
        finally:
            probe.close()

    def _serve(self) -> None:
        while not self._stopping.is_set():
            try:
                connection = self._listener.accept()
            except AuthenticationError:
                continue
            except (OSError, EOFError):
                if not self._stopping.is_set():
                    continue
                return

            with self._state_lock:
                if self._stopping.is_set():
                    connection.close()
                    return
                worker = threading.Thread(
                    target=self._serve_connection,
                    args=(connection,),
                    name="secretmanager-local-ipc-request",
                    daemon=True,
                )
                self._connections.add(connection)
                self._workers.add(worker)
                worker.start()

    def _serve_connection(self, connection) -> None:
        worker = threading.current_thread()
        try:
            with connection:
                while not self._stopping.is_set():
                    if connection.poll(0.1):
                        break
                else:
                    return

                if self._stopping.is_set():
                    return
                request = json.loads(
                    connection.recv_bytes(MAX_REQUEST_BYTES).decode("utf-8")
                )
                if request == {"operation": "stop"}:
                    return
                if self._stopping.is_set():
                    return

                response = self._handle_request(request)
                if self._stopping.is_set():
                    return
                encoded_response = json.dumps(
                    response,
                    separators=(",", ":"),
                ).encode("utf-8")
                if len(encoded_response) > MAX_RESPONSE_BYTES:
                    encoded_response = b'{"ok":false,"error":"response_too_large"}'
                if not self._stopping.is_set():
                    connection.send_bytes(encoded_response)
        except (AuthenticationError, EOFError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        except Exception:
            # A lock can invalidate the vault key during a lookup. Discard the
            # failed request without sending exception details to the client.
            pass
        finally:
            with self._state_lock:
                self._connections.discard(connection)
                self._workers.discard(worker)
                if self._transport_closed and not self._workers:
                    self._closed_event.set()

    def _handle_request(self, request: object) -> dict[str, object]:
        if not isinstance(request, dict) or request.get("operation") != "get":
            return {"ok": False, "error": "invalid_request"}
        names = request.get("names")
        if (
            not isinstance(names, list)
            or not names
            or len(names) > MAX_SECRET_NAMES
            or any(not isinstance(name, str) or not name for name in names)
            or len(set(names)) != len(names)
        ):
            return {"ok": False, "error": "invalid_names"}

        secrets_by_name: dict[str, object] = {}
        missing: list[str] = []
        denied: list[str] = []
        for name in names:
            if self._stopping.is_set():
                return {"ok": False, "error": "server_stopping"}
            secret = self.get_secret(name)
            if self._stopping.is_set():
                return {"ok": False, "error": "server_stopping"}
            if secret is None:
                missing.append(name)
                continue
            if not bool(getattr(secret, "allow_cli", False)):
                denied.append(name)
                continue
            value = getattr(secret, "value", None)
            if not isinstance(value, str):
                return {"ok": False, "error": "invalid_secret"}
            secrets_by_name[name] = {
                "value": value,
                "status": get_expiry_status(
                    getattr(secret, "expires_on", None),
                    getattr(secret, "expires_at_time", None),
                ),
            }

        if missing:
            return {"ok": False, "error": "secret_not_found", "names": missing}
        if denied:
            return {"ok": False, "error": "cli_not_allowed", "names": denied}
        return {"ok": True, "secrets": secrets_by_name}

    def close(self) -> None:
        with self._state_lock:
            if self._closing_started:
                return
            self._closing_started = True
            self._stopping.set()
            connections = list(self._connections)

        # Break client waits immediately. Request workers may still be unwinding,
        # but they can no longer send a response after the stop event is set.
        for connection in connections:
            try:
                connection.close()
            except OSError:
                pass

        # Wake Listener.accept() so the endpoint can be closed synchronously.
        if self._listener is not None:
            try:
                with Client(
                    self.address,
                    family=self.family,
                    authkey=self.token,
                ) as connection:
                    connection.send_bytes(b'{"operation":"stop"}')
            except (AuthenticationError, EOFError, OSError):
                pass

            listener_thread = self._thread
            if listener_thread is not None:
                listener_thread.join()
            listener = self._listener
            if listener is not None:
                listener.close()
            self._listener = None

        self._remove_endpoint_files()

        with self._state_lock:
            self._transport_closed = True
            if not self._workers:
                self._closed_event.set()

    def _remove_endpoint_files(self) -> None:
        try:
            self.token_path.unlink()
        except FileNotFoundError:
            pass

        if self.family == "AF_UNIX":
            path = Path(self.address)
            try:
                if stat.S_ISSOCK(path.lstat().st_mode):
                    path.unlink()
            except FileNotFoundError:
                pass

    def wait_closed(self, timeout: float | None = None) -> bool:
        """Wait for interrupted request workers to finish unwinding."""
        return self._closed_event.wait(timeout)
