from ..domain.secret import Secret
from .secret_repository import SecretRepository


class InMemorySecretRepository(SecretRepository):
    def __init__(self):
        self._secrets: list[Secret] = []

    def save(self, secret: Secret) -> None:
        self._secrets.append(secret)

    def list(self) -> list[Secret]:
        return list(self._secrets)

    def get(self, name: str) -> Secret | None:
        for secret in self._secrets:
            if secret.name == name:
                return secret

        return None

    def delete(self, name: str) -> bool:
        secret = self.get(name)

        if secret is None:
            return False

        self._secrets.remove(secret)

        return True

    def update(
        self,
        current_name: str,
        secret: Secret,
    ) -> None:
        current = self.get(current_name)

        if current is None:
            raise ValueError("Secret not found.")

        current.name = secret.name
        current.value = secret.value
        current.note = secret.note
        current.expires_on = secret.expires_on
        current.expires_at_time = secret.expires_at_time