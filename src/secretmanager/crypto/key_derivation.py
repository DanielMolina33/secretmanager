import os

from argon2.low_level import (
    Type,
    hash_secret_raw,
)

from ..domain.master_password import normalize_master_password


SALT_SIZE = 16
KEY_SIZE = 32

TIME_COST = 3
MEMORY_COST = 64 * 1024
PARALLELISM = 4


def generate_salt() -> bytes:
    return os.urandom(SALT_SIZE)


def derive_key(
    password: str,
    salt: bytes,
) -> bytes:
    if not password:
        raise ValueError("Password cannot be empty.")

    if len(salt) != SALT_SIZE:
        raise ValueError(
            f"Salt must be exactly {SALT_SIZE} bytes."
        )

    return hash_secret_raw(
        secret=normalize_master_password(password).encode("utf-8"),
        salt=salt,
        time_cost=TIME_COST,
        memory_cost=MEMORY_COST,
        parallelism=PARALLELISM,
        hash_len=KEY_SIZE,
        type=Type.ID,
    )