import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


NONCE_SIZE = 12


def encrypt_key(
    key_to_encrypt: bytes,
    encryption_key: bytes,
) -> tuple[bytes, bytes]:
    if len(encryption_key) != 32:
        raise ValueError(
            "Encryption key must be exactly 32 bytes."
        )

    nonce = os.urandom(NONCE_SIZE)

    encrypted_key = AESGCM(encryption_key).encrypt(
        nonce,
        key_to_encrypt,
        None,
    )

    return nonce, encrypted_key


def decrypt_key(
    encrypted_key: bytes,
    nonce: bytes,
    encryption_key: bytes,
) -> bytes:
    if len(encryption_key) != 32:
        raise ValueError(
            "Encryption key must be exactly 32 bytes."
        )

    if len(nonce) != NONCE_SIZE:
        raise ValueError(
            f"Nonce must be exactly {NONCE_SIZE} bytes."
        )

    return AESGCM(encryption_key).decrypt(
        nonce,
        encrypted_key,
        None,
    )