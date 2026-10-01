from cryptography.exceptions import InvalidTag

from .crypto.vault_keys import (
    ProtectedKey,
    VaultKeyManager,
)


class Vault:
    def __init__(
        self,
        protected_key: ProtectedKey,
    ):
        self._protected_key = protected_key
        self._dek: bytes | None = None

    @property
    def is_unlocked(self) -> bool:
        return self._dek is not None

    def unlock(self, password: str) -> None:
        try:
            dek = VaultKeyManager.unlock(
                password,
                self._protected_key,
            )
        except InvalidTag as error:
            raise ValueError(
                "Invalid master password."
            ) from error

        self._dek = dek

    def lock(self) -> None:
        self._dek = None

    def get_dek(self) -> bytes:
        if self._dek is None:
            raise RuntimeError(
                "Vault is locked."
            )

        return self._dek