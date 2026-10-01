import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


NONCE_SIZE = 12
KEY_SIZE = 32

_SECRET_KEY_INFO = b"secretmanager/secret-value/v1"


def _derive_secret_key(
    dek: bytes,
) -> bytes:
    if len(dek) != KEY_SIZE:
        raise ValueError(
            "DEK must be exactly 32 bytes."
        )

    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=None,
        info=_SECRET_KEY_INFO,
    ).derive(dek)


def encrypt_secret(
    value: str,
    dek: bytes,
) -> tuple[bytes, bytes]:
    encryption_key = _derive_secret_key(dek)

    nonce = os.urandom(NONCE_SIZE)

    encrypted_value = AESGCM(
        encryption_key
    ).encrypt(
        nonce,
        value.encode("utf-8"),
        None,
    )

    return nonce, encrypted_value


def decrypt_secret(
    encrypted_value: bytes,
    nonce: bytes,
    dek: bytes,
) -> str:
    encryption_key = _derive_secret_key(dek)

    if len(nonce) != NONCE_SIZE:
        raise ValueError(
            f"Nonce must be exactly {NONCE_SIZE} bytes."
        )

    decrypted_value = AESGCM(
        encryption_key
    ).decrypt(
        nonce,
        encrypted_value,
        None,
    )

    return decrypted_value.decode("utf-8")