import base64
import json
from dataclasses import dataclass

from .vault_keys import ProtectedKey


@dataclass(frozen=True)
class KeyEnvelope:
    salt: bytes
    nonce: bytes
    encrypted_dek: bytes
    recovery_nonce: bytes | None = None
    recovery_encrypted_dek: bytes | None = None

    @property
    def has_recovery_key(self) -> bool:
        return self.recovery_nonce is not None and self.recovery_encrypted_dek is not None

    @classmethod
    def from_protected_key(cls, protected_key: ProtectedKey) -> "KeyEnvelope":
        return cls(
            salt=protected_key.salt,
            nonce=protected_key.nonce,
            encrypted_dek=protected_key.encrypted_dek,
            recovery_nonce=protected_key.recovery_nonce,
            recovery_encrypted_dek=protected_key.recovery_encrypted_dek,
        )

    def to_protected_key(self) -> ProtectedKey:
        return ProtectedKey(
            salt=self.salt,
            nonce=self.nonce,
            encrypted_dek=self.encrypted_dek,
            recovery_nonce=self.recovery_nonce,
            recovery_encrypted_dek=self.recovery_encrypted_dek,
        )

    def to_bytes(self) -> bytes:
        data = {
            "version": 2 if self.has_recovery_key else 1,
            "salt": base64.b64encode(self.salt).decode("ascii"),
            "nonce": base64.b64encode(self.nonce).decode("ascii"),
            "encrypted_dek": base64.b64encode(self.encrypted_dek).decode("ascii"),
        }
        if self.has_recovery_key:
            data["recovery_nonce"] = base64.b64encode(self.recovery_nonce).decode("ascii")
            data["recovery_encrypted_dek"] = base64.b64encode(self.recovery_encrypted_dek).decode("ascii")

        return json.dumps(data, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "KeyEnvelope":
        payload = json.loads(data.decode("utf-8"))
        version = payload.get("version")
        if version not in (1, 2):
            raise ValueError("Unsupported key envelope version.")

        recovery_nonce = payload.get("recovery_nonce")
        recovery_encrypted_dek = payload.get("recovery_encrypted_dek")
        if version == 1 and (recovery_nonce is not None or recovery_encrypted_dek is not None):
            raise ValueError("Invalid key envelope.")
        if version == 2 and (recovery_nonce is None or recovery_encrypted_dek is None):
            raise ValueError("Invalid key envelope.")

        decode = lambda value: base64.b64decode(value, validate=True)
        return cls(
            salt=decode(payload["salt"]),
            nonce=decode(payload["nonce"]),
            encrypted_dek=decode(payload["encrypted_dek"]),
            recovery_nonce=decode(recovery_nonce) if recovery_nonce is not None else None,
            recovery_encrypted_dek=(
                decode(recovery_encrypted_dek)
                if recovery_encrypted_dek is not None
                else None
            ),
        )
