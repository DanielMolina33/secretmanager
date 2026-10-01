from dataclasses import dataclass

from ..crypto.key_encryption import (
    decrypt_key,
    encrypt_key,
)
from ..crypto.key_derivation import (
    derive_key,
    generate_salt,
)
from ..crypto.keys import generate_dek


@dataclass(frozen=True)
class ProtectedKey:
    salt: bytes
    nonce: bytes
    encrypted_dek: bytes


class VaultKeyManager:
    @staticmethod
    def create(password: str) -> tuple[bytes, ProtectedKey]:
        salt = generate_salt()
        kek = derive_key(password, salt)
        dek = generate_dek()

        nonce, encrypted_dek = encrypt_key(
            dek,
            kek,
        )

        protected_key = ProtectedKey(
            salt=salt,
            nonce=nonce,
            encrypted_dek=encrypted_dek,
        )

        return dek, protected_key

    @staticmethod
    def unlock(
        password: str,
        protected_key: ProtectedKey,
    ) -> bytes:
        kek = derive_key(
            password,
            protected_key.salt,
        )

        return decrypt_key(
            protected_key.encrypted_dek,
            protected_key.nonce,
            kek,
        )