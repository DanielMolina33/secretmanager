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
from ..domain.master_password import validate_new_master_password


@dataclass(frozen=True)
class ProtectedKey:
    salt: bytes
    nonce: bytes
    encrypted_dek: bytes
    recovery_nonce: bytes | None = None
    recovery_encrypted_dek: bytes | None = None

    @property
    def has_recovery_key(self) -> bool:
        return self.recovery_nonce is not None and self.recovery_encrypted_dek is not None


class VaultKeyManager:
    @staticmethod
    def create(password: str) -> tuple[bytes, ProtectedKey]:
        validate_new_master_password(password)
        dek = generate_dek()
        return dek, VaultKeyManager.wrap_dek(password, dek)

    @staticmethod
    def wrap_dek(password: str, dek: bytes) -> ProtectedKey:
        validate_new_master_password(password)
        salt = generate_salt()
        kek = derive_key(password, salt)
        nonce, encrypted_dek = encrypt_key(dek, kek)
        return ProtectedKey(
            salt=salt,
            nonce=nonce,
            encrypted_dek=encrypted_dek,
        )

    @staticmethod
    def wrap_dek_with_recovery(dek: bytes, recovery_key: bytes) -> tuple[bytes, bytes]:
        return encrypt_key(dek, recovery_key)

    @staticmethod
    def unlock_with_recovery(recovery_key: bytes, protected_key: ProtectedKey) -> bytes:
        if not protected_key.has_recovery_key:
            raise ValueError("No recovery kit is configured.")
        return decrypt_key(
            protected_key.recovery_encrypted_dek,
            protected_key.recovery_nonce,
            recovery_key,
        )

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