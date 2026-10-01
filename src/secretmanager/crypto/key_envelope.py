import base64
import json
from dataclasses import dataclass

from .vault_keys import ProtectedKey


@dataclass(frozen=True)
class KeyEnvelope:
    salt: bytes
    nonce: bytes
    encrypted_dek: bytes

    @classmethod
    def from_protected_key(
        cls,
        protected_key: ProtectedKey,
    ) -> "KeyEnvelope":
        return cls(
            salt=protected_key.salt,
            nonce=protected_key.nonce,
            encrypted_dek=protected_key.encrypted_dek,
        )

    def to_protected_key(self) -> ProtectedKey:
        return ProtectedKey(
            salt=self.salt,
            nonce=self.nonce,
            encrypted_dek=self.encrypted_dek,
        )

    def to_bytes(self) -> bytes:
        data = {
            "version": 1,
            "salt": base64.b64encode(
                self.salt
            ).decode("ascii"),
            "nonce": base64.b64encode(
                self.nonce
            ).decode("ascii"),
            "encrypted_dek": base64.b64encode(
                self.encrypted_dek
            ).decode("ascii"),
        }

        return json.dumps(
            data,
            separators=(",", ":"),
        ).encode("utf-8")

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
    ) -> "KeyEnvelope":
        payload = json.loads(
            data.decode("utf-8")
        )

        if payload.get("version") != 1:
            raise ValueError(
                "Unsupported key envelope version."
            )

        return cls(
            salt=base64.b64decode(
                payload["salt"]
            ),
            nonce=base64.b64decode(
                payload["nonce"]
            ),
            encrypted_dek=base64.b64decode(
                payload["encrypted_dek"]
            ),
        )