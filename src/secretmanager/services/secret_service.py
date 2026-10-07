import re
from datetime import date, datetime, time
from ..repositories.secret_repository import SecretRepository

from ..domain.exceptions import (
    DuplicateSecretError,
    EmptySecretValueError,
    InvalidSecretNameError,
)
from ..domain.secret import Secret
from ..domain.secret_listing import SecretListPage


SECRET_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SecretService:
    def __init__(self, repository: SecretRepository):
        self.repository = repository

    def create(
        self,
        name: str,
        value: str,
        note: str = "",
        expires_on: date | None = None,
        expires_at_time: time | None = None,
        allow_cli: bool = False,
    ) -> Secret:
        self._validate_name(name)
        self._validate_value(value)
        expires_at_time = self._normalize_expiry(expires_on, expires_at_time)

        if self.get(name) is not None:
            raise DuplicateSecretError(
                f"A secret named '{name}' already exists."
            )

        secret = Secret(
            name=name,
            value=value,
            note=note,
            expires_on=expires_on,
            expires_at_time=expires_at_time,
            allow_cli=allow_cli,
        )

        self.repository.save(secret)

        return secret

    def list(self) -> list[Secret]:
        return self.repository.list()

    def list_page(
        self,
        *,
        search_text: str = "",
        status: str = "all",
        descending: bool = False,
        page_index: int = 0,
        page_size: int = 25,
        now: datetime | None = None,
    ) -> SecretListPage:
        return self.repository.list_page(
            search_text=search_text,
            status=status,
            descending=descending,
            page_index=page_index,
            page_size=page_size,
            now=now,
        )

    def next_status_transition(
        self,
        *,
        now: datetime | None = None,
    ) -> datetime | None:
        return self.repository.next_status_transition(now=now)

    def get(self, name: str) -> Secret | None:
        return self.repository.get(name)

    def update(
        self,
        current_name: str,
        name: str,
        value: str,
        note: str = "",
        expires_on: date | None = None,
        expires_at_time: time | None = None,
        allow_cli: bool | None = None,
    ) -> Secret:
        secret = self.get(current_name)

        if secret is None:
            raise ValueError("Secret not found.")

        self._validate_name(name)
        self._validate_value(value)
        expires_at_time = self._normalize_expiry(expires_on, expires_at_time)

        if name != current_name and self.get(name) is not None:
            raise DuplicateSecretError(
                f"A secret named '{name}' already exists."
            )

        updated_secret = Secret(
            name=name,
            value=value,
            note=note,
            expires_on=expires_on,
            expires_at_time=expires_at_time,
            allow_cli=secret.allow_cli if allow_cli is None else allow_cli,
        )

        self.repository.update(
            current_name=current_name,
            secret=updated_secret,
        )

        return updated_secret

    def delete(self, name: str) -> bool:
        return self.repository.delete(name)

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name:
            raise InvalidSecretNameError(
                "Secret name cannot be empty."
            )

        if not SECRET_NAME_PATTERN.fullmatch(name):
            raise InvalidSecretNameError(
                "Secret name must be a valid environment variable name."
            )

    @staticmethod
    def _validate_value(value: str) -> None:
        if not value:
            raise EmptySecretValueError(
                "Secret value cannot be empty."
            )
    @staticmethod
    def _normalize_expiry(
        expires_on: date | None,
        expires_at_time: time | None,
    ) -> time | None:
        if expires_at_time is None:
            return None
        if expires_on is None:
            raise ValueError("An expiry time requires an expiry date.")
        return time(expires_at_time.hour, expires_at_time.minute)
