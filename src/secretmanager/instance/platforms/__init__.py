"""Platform-specific instance-lock and local activation configuration."""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlatformBackend:
    create_lock: Any
    configure_server: Any
    configure_client: Any
    recover_stale_server: bool


def _user_key_material() -> str:
    if os.name == "nt":
        import getpass

        domain = os.environ.get("USERDOMAIN", "")
        return f"{domain}\\{getpass.getuser()}".casefold()
    return str(os.getuid())


def user_scope() -> str:
    return hashlib.sha256(_user_key_material().encode("utf-8")).hexdigest()[:24]


def get_backend() -> tuple[PlatformBackend, str]:
    if sys.platform == "win32":
        from .windows import create_backend
    elif sys.platform == "darwin":
        from .macos import create_backend
    elif sys.platform.startswith("linux"):
        from .linux import create_backend
    else:
        raise RuntimeError(f"Single-instance coordination is unsupported on {sys.platform}.")
    return create_backend(user_scope())
