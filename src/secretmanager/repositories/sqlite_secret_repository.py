from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ..crypto.secret_encryption import (
    decrypt_secret,
    encrypt_secret,
)
from ..database.models import SecretModel
from ..domain.secret import Secret
from .secret_repository import SecretRepository


class SqliteSecretRepository(SecretRepository):
    def __init__(
        self,
        session_factory: sessionmaker,
        encryption_key_provider: Callable[[], bytes],
    ):
        self.session_factory = session_factory
        self.encryption_key_provider = encryption_key_provider

    def save(self, secret: Secret) -> None:
        encryption_key = self.encryption_key_provider()

        value_nonce, encrypted_value = encrypt_secret(
            secret.value,
            encryption_key,
        )

        now = datetime.now()

        model = SecretModel(
            name=secret.name,
            value=encrypted_value,
            value_nonce=value_nonce,
            note=secret.note,
            expires_on=secret.expires_on,
            expires_at_time=secret.expires_at_time,
            created_at=now,
            updated_at=now,
        )

        with self.session_factory.begin() as session:
            session.add(model)

    def list(self) -> list[Secret]:
        with self.session_factory() as session:
            statement = select(SecretModel).order_by(SecretModel.name)
            models = session.scalars(statement).all()

            return [self._to_domain(model) for model in models]

    def get(self, name: str) -> Secret | None:
        with self.session_factory() as session:
            statement = select(SecretModel).where(
                SecretModel.name == name
            )

            model = session.scalars(statement).first()

            if model is None:
                return None

            return self._to_domain(model)

    def update(
        self,
        current_name: str,
        secret: Secret,
    ) -> None:
        encryption_key = self.encryption_key_provider()

        value_nonce, encrypted_value = encrypt_secret(
            secret.value,
            encryption_key,
        )

        with self.session_factory.begin() as session:
            statement = select(SecretModel).where(
                SecretModel.name == current_name
            )

            model = session.scalars(statement).first()

            if model is None:
                raise ValueError("Secret not found.")

            model.name = secret.name
            model.value = encrypted_value
            model.value_nonce = value_nonce
            model.note = secret.note
            model.expires_on = secret.expires_on
            model.expires_at_time = secret.expires_at_time
            model.updated_at = datetime.now()

    def delete(self, name: str) -> bool:
        with self.session_factory.begin() as session:
            statement = select(SecretModel).where(
                SecretModel.name == name
            )

            model = session.scalars(statement).first()

            if model is None:
                return False

            session.delete(model)
            return True

    def _to_domain(self, model: SecretModel) -> Secret:
        encryption_key = self.encryption_key_provider()

        value = decrypt_secret(
            model.value,
            model.value_nonce,
            encryption_key,
        )

        return Secret(
            name=model.name,
            value=value,
            note=model.note,
            expires_on=model.expires_on,
            expires_at_time=model.expires_at_time,
        )
