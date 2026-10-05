from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_RECOVERY_KEY_SIZE = 32
_CHECKSUM_SIZE = 4
_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


def generate_recovery_kit() -> tuple[str, bytes]:
    """Return a one-time-display recovery code and its 256-bit key."""
    key = secrets.token_bytes(_RECOVERY_KEY_SIZE)
    checksum = hashlib.sha256(key).digest()[:_CHECKSUM_SIZE]
    encoded = base64.b32encode(key + checksum).decode("ascii").rstrip("=")
    code = "-".join(encoded[index:index + 5] for index in range(0, len(encoded), 5))
    return code, key


def recovery_key_from_code(code: str) -> bytes:
    compact = "".join(code.split()).replace("-", "").upper()
    if not compact or any(character not in _ALPHABET for character in compact):
        raise ValueError("Invalid recovery kit.")

    padded = compact + "=" * ((-len(compact)) % 8)
    try:
        decoded = base64.b32decode(padded, casefold=False)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("Invalid recovery kit.") from error

    if len(decoded) != _RECOVERY_KEY_SIZE + _CHECKSUM_SIZE:
        raise ValueError("Invalid recovery kit.")

    key = decoded[:_RECOVERY_KEY_SIZE]
    supplied_checksum = decoded[_RECOVERY_KEY_SIZE:]
    expected_checksum = hashlib.sha256(key).digest()[:_CHECKSUM_SIZE]
    if not hmac.compare_digest(supplied_checksum, expected_checksum):
        raise ValueError("Invalid recovery kit.")

    return key
