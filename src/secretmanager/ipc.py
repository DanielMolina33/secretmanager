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
from multiprocessing.connection import AuthenticationError, Client, Listener
from pathlib import Path
from typing import Callable


TOKEN_FILENAME = "ipc-token"
SOCKET_FILENAME = "secretmanager.sock"
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_SECRET_NAMES = 128


def _endpoint(data_dir: Path) -> tuple[str, str]:
    if sys.platform == "win32":
        identity = str(data_dir.resolve()).casefold().encode("utf-8")
        suffix = hashlib.sha256(identity).hexdigest()[:24]
        return rf"\\.\pipe\secretmanager-{suffix}", "AF_PIPE"

    path = data_dir / SOCKET_FILENAME
    if len(os.fsencode(path)) >= 100:
        raise OSError("The portable path is too long for a local Unix socket.")
    return str(path), "AF_UNIX"


def request_secrets(data_dir: Path, names: list[str]) -> dict[str, str]:
    token_path = data_dir / TOKEN_FILENAME
    token = token_path.read_bytes()
    if len(token) != 32:
        raise ValueError("The local IPC session token is invalid.")

    address, family = _endpoint(data_dir)
    with Client(address, family=family, authkey=token) as connection:
        connection.send_bytes(json.dumps(
            {"operation": "get", "names": names},
            separators=(",", ":"),
        ).encode("utf-8"))
        response = json.loads(connection.recv_bytes(MAX_RESPONSE_BYTES).decode("utf-8"))

    if not isinstance(response, dict) or not response.get("ok"):
        raise RuntimeError("The vault rejected the local CLI request.")
    secrets_by_name = response.get("secrets")
    if not isinstance(secrets_by_name, dict):
        raise RuntimeError("The vault returned an invalid local IPC response.")
    missing = response.get("missing", [])
    if missing:
        raise KeyError(", ".join(str(name) for name in missing))
    if set(secrets_by_name) != set(names) or any(
        not isinstance(value, str) for value in secrets_by_name.values()
    ):
        raise RuntimeError("The vault returned an incomplete local IPC response.")
    return secrets_by_name


class LocalSecretServer:
    """Serves secret values only to a client holding this session's token."""

    def __init__(self, data_dir: Path, get_secret: Callable[[str], object | None]):
        self.data_dir = data_dir
        self.get_secret = get_secret
        self.token_path = data_dir / TOKEN_FILENAME
        self.token = secrets.token_bytes(32)
        self.address, self.family = _endpoint(data_dir)
        self._listener = None
        self._thread = None
        self._stopping = threading.Event()

    def start(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.family == "AF_UNIX":
            self._remove_stale_socket()

        listener = Listener(
            self.address,
            family=self.family,
            authkey=self.token,
        )
        try:
            if self.family == "AF_UNIX":
                Path(self.address).chmod(0o600)
            self._write_token()
        except Exception:
            listener.close()
            raise

        self._listener = listener
        self._thread = threading.Thread(
            target=self._serve,
            name="secretmanager-local-ipc",
            daemon=True,
        )
        self._thread.start()

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
                # An unauthenticated local client receives no secret data.
                continue
            except (OSError, EOFError):
                if not self._stopping.is_set():
                    continue
                return

            with connection:
                try:
                    if not connection.poll(5.0):
                        continue
                    request = json.loads(
                        connection.recv_bytes(MAX_REQUEST_BYTES).decode("utf-8")
                    )
                    if request == {"operation": "stop"}:
                        connection.send_bytes(b'{"ok":true}')
                        self._stopping.set()
                        return
                    response = self._handle_request(request)
                    encoded_response = json.dumps(
                        response,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    if len(encoded_response) > MAX_RESPONSE_BYTES:
                        encoded_response = b'{"ok":false,"error":"response_too_large"}'
                    connection.send_bytes(encoded_response)
                except (EOFError, OSError, UnicodeDecodeError, json.JSONDecodeError):
                    # Malformed clients are discarded without logging request data.
                    continue

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

        result: dict[str, str] = {}
        missing: list[str] = []
        for name in names:
            secret = self.get_secret(name)
            if secret is None:
                missing.append(name)
            else:
                value = getattr(secret, "value", None)
                if not isinstance(value, str):
                    return {"ok": False, "error": "invalid_secret"}
                result[name] = value
        return {"ok": True, "secrets": result, "missing": missing}

    def close(self) -> None:
        listener = self._listener
        if listener is None:
            return

        # Wake accept() through the same authenticated, local-only endpoint.
        try:
            with Client(self.address, family=self.family, authkey=self.token) as connection:
                connection.send_bytes(b'{"operation":"stop"}')
                if connection.poll(2.0):
                    connection.recv_bytes(MAX_REQUEST_BYTES)
        except (AuthenticationError, OSError, EOFError):
            pass

        self._stopping.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3.0)
        listener.close()
        self._listener = None
        self._thread = None

        try:
            self.token_path.unlink()
        except FileNotFoundError:
            pass
        if self.family == "AF_UNIX":
            try:
                Path(self.address).unlink()
            except FileNotFoundError:
                pass
