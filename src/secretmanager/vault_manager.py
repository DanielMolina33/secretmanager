from dataclasses import dataclass
from math import ceil
from pathlib import Path
from time import monotonic

from cryptography.exceptions import InvalidTag

from .crypto.key_envelope import KeyEnvelope
from .crypto.key_storage import KeyStorage
from .crypto.recovery_kit import generate_recovery_kit, recovery_key_from_code
from .crypto.vault_keys import ProtectedKey, VaultKeyManager
from .domain.master_password import validate_new_master_password
from .vault import Vault


class UnlockAttemptError(ValueError):
    """Invalid unlock attempt, optionally carrying a retry delay."""

    def __init__(self, retry_after_seconds: int = 0):
        super().__init__("Invalid master password.")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class PendingRecoveryKit:
    code: str
    expected_key: ProtectedKey
    protected_key: ProtectedKey


class VaultManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.database_path = data_dir / "vault.db"
        self.key_storage = KeyStorage(data_dir / "vault.key")
        self._vault: Vault | None = None
        self._failed_unlock_attempts = 0
        self._unlock_blocked_until = 0.0

    @property
    def exists(self) -> bool:
        return self.key_storage.path.exists()

    @property
    def recovery_configured(self) -> bool:
        return self.exists and self.key_storage.load().has_recovery_key

    @property
    def vault(self) -> Vault:
        if self._vault is None:
            raise RuntimeError("Vault has not been created.")
        return self._vault

    def create(self, password: str) -> Vault:
        if self.exists:
            raise FileExistsError("Vault already exists.")

        _, protected_key = VaultKeyManager.create(password)
        self.key_storage.save(KeyEnvelope.from_protected_key(protected_key))
        self._vault = Vault(protected_key)
        self._vault.unlock(password)
        return self._vault

    @property
    def unlock_cooldown_remaining(self) -> int:
        return max(0, ceil(self._unlock_blocked_until - monotonic()))

    def unlock(self, password: str) -> Vault:
        if not self.exists:
            raise FileNotFoundError("Vault does not exist.")

        remaining = self.unlock_cooldown_remaining
        if remaining:
            raise UnlockAttemptError(remaining)

        protected_key = self.key_storage.load().to_protected_key()
        vault = Vault(protected_key)
        try:
            vault.unlock(password)
        except ValueError as error:
            if str(error) != "Invalid master password.":
                raise
            self._failed_unlock_attempts += 1
            retry_after = 0
            if self._failed_unlock_attempts >= 3:
                retry_after = min(5 * 2 ** (self._failed_unlock_attempts - 3), 300)
                self._unlock_blocked_until = monotonic() + retry_after
            raise UnlockAttemptError(retry_after) from error

        self._failed_unlock_attempts = 0
        self._unlock_blocked_until = 0.0
        self._vault = vault
        return vault

    def verify_master_password(self, password: str) -> bool:
        self._protected_key_and_dek(password)
        return True

    def prepare_recovery_kit(self, password: str) -> PendingRecoveryKit:
        vault = self._require_unlocked_vault()
        current_key, dek = self._protected_key_and_dek(password)
        if dek != vault.get_dek():
            raise ValueError("The active vault key changed.")

        code, recovery_key = generate_recovery_kit()
        nonce, encrypted_dek = VaultKeyManager.wrap_dek_with_recovery(dek, recovery_key)
        protected_key = ProtectedKey(
            salt=current_key.salt,
            nonce=current_key.nonce,
            encrypted_dek=current_key.encrypted_dek,
            recovery_nonce=nonce,
            recovery_encrypted_dek=encrypted_dek,
        )
        return PendingRecoveryKit(code, current_key, protected_key)

    def commit_recovery_kit(self, pending: PendingRecoveryKit) -> None:
        vault = self._require_unlocked_vault()
        current_key = self.key_storage.load().to_protected_key()
        if current_key != pending.expected_key:
            raise RuntimeError("The vault key changed before the recovery kit was saved.")
        if not pending.protected_key.has_recovery_key:
            raise ValueError("Invalid pending recovery kit.")
        recovery_key = recovery_key_from_code(pending.code)
        try:
            recovered_dek = VaultKeyManager.unlock_with_recovery(recovery_key, pending.protected_key)
        except InvalidTag as error:
            raise ValueError("Invalid pending recovery kit.") from error
        if recovered_dek != vault.get_dek():
            raise ValueError("The active vault key changed.")

        self.key_storage.save(KeyEnvelope.from_protected_key(pending.protected_key))
        vault.replace_protected_key(pending.protected_key)

    def disable_recovery_kit(self, password: str) -> None:
        vault = self._require_unlocked_vault()
        current_key, dek = self._protected_key_and_dek(password)
        if dek != vault.get_dek():
            raise ValueError("The active vault key changed.")
        if not current_key.has_recovery_key:
            return

        protected_key = ProtectedKey(
            salt=current_key.salt,
            nonce=current_key.nonce,
            encrypted_dek=current_key.encrypted_dek,
        )
        self.key_storage.save(KeyEnvelope.from_protected_key(protected_key))
        vault.replace_protected_key(protected_key)

    def recover(self, recovery_code: str, new_password: str) -> Vault:
        if not self.exists:
            raise FileNotFoundError("Vault does not exist.")
        validate_new_master_password(new_password)
        current_key = self.key_storage.load().to_protected_key()
        recovery_key = recovery_key_from_code(recovery_code)
        try:
            dek = VaultKeyManager.unlock_with_recovery(recovery_key, current_key)
        except InvalidTag as error:
            raise ValueError("Invalid recovery kit.") from error

        # A successful recovery consumes the presented kit. A new kit is an explicit action.
        protected_key = VaultKeyManager.wrap_dek(new_password, dek)
        vault = Vault(protected_key)
        vault.unlock(new_password)
        self.key_storage.save(KeyEnvelope.from_protected_key(protected_key))
        self._failed_unlock_attempts = 0
        self._unlock_blocked_until = 0.0
        self._vault = vault
        return vault

    def change_master_password(self, current_password: str, new_password: str) -> None:
        vault = self._require_unlocked_vault()
        validate_new_master_password(new_password)
        current_key, dek = self._protected_key_and_dek(current_password)
        if dek != vault.get_dek():
            raise ValueError("The active vault key changed.")

        password_key = VaultKeyManager.wrap_dek(new_password, dek)
        protected_key = ProtectedKey(
            salt=password_key.salt,
            nonce=password_key.nonce,
            encrypted_dek=password_key.encrypted_dek,
            recovery_nonce=current_key.recovery_nonce,
            recovery_encrypted_dek=current_key.recovery_encrypted_dek,
        )
        self.key_storage.save(KeyEnvelope.from_protected_key(protected_key))
        vault.replace_protected_key(protected_key)

    def _protected_key_and_dek(self, password: str) -> tuple[ProtectedKey, bytes]:
        protected_key = self.key_storage.load().to_protected_key()
        try:
            dek = VaultKeyManager.unlock(password, protected_key)
        except InvalidTag as error:
            raise ValueError("Invalid master password.") from error
        return protected_key, dek

    def _require_unlocked_vault(self) -> Vault:
        if self._vault is None or not self._vault.is_unlocked:
            raise RuntimeError("Vault must be unlocked.")
        return self._vault
