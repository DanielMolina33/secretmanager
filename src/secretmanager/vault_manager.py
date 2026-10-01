from pathlib import Path

from .crypto.key_envelope import KeyEnvelope
from .crypto.key_storage import KeyStorage
from .crypto.vault_keys import VaultKeyManager
from .vault import Vault


class VaultManager:
    def __init__(
        self,
        data_dir: Path,
    ):
        self.data_dir = data_dir

        self.database_path = (
            data_dir / "vault.db"
        )

        self.key_storage = KeyStorage(
            data_dir / "vault.key"
        )

        self._vault: Vault | None = None

    @property
    def exists(self) -> bool:
        return self.key_storage.path.exists()

    @property
    def vault(self) -> Vault:
        if self._vault is None:
            raise RuntimeError(
                "Vault has not been created."
            )

        return self._vault

    def create(
        self,
        password: str,
    ) -> Vault:
        if self.exists:
            raise FileExistsError(
                "Vault already exists."
            )

        _, protected_key = VaultKeyManager.create(
            password
        )

        envelope = KeyEnvelope.from_protected_key(
            protected_key
        )

        self.key_storage.save(envelope)

        self._vault = Vault(protected_key)

        self._vault.unlock(password)

        return self._vault

    def unlock(
        self,
        password: str,
    ) -> Vault:
        if not self.exists:
            raise FileNotFoundError(
                "Vault does not exist."
            )

        envelope = self.key_storage.load()

        protected_key = (
            envelope.to_protected_key()
        )

        vault = Vault(protected_key)

        vault.unlock(password)

        self._vault = vault

        return vault