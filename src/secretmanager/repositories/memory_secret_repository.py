from datetime import datetime

from ..domain.expiry import (
    EXPIRED,
    EXPIRING,
    VALID,
    get_expiry_status,
    get_next_expiry_transition,
)
from ..domain.secret import Secret
from ..domain.secret_listing import SecretListPage, SecretSummary
from .secret_repository import SecretRepository


class InMemorySecretRepository(SecretRepository):
    def __init__(self):
        self._secrets: list[Secret] = []

    def save(self, secret: Secret) -> None:
        self._secrets.append(secret)

    def list(self) -> list[Secret]:
        return list(self._secrets)

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
        if page_size < 1:
            raise ValueError("page_size must be greater than zero")
        if status not in {"all", VALID, EXPIRING, EXPIRED}:
            raise ValueError(f"Unknown secret status: {status}")

        current = now or datetime.now()
        query = search_text.strip().lower()
        counts = {VALID: 0, EXPIRING: 0, EXPIRED: 0}
        matching = []

        for secret in self._secrets:
            secret_status = get_expiry_status(
                secret.expires_on,
                secret.expires_at_time,
                now=current,
            )
            counts[secret_status] += 1

            if query and query not in secret.name.lower() and query not in secret.note.lower():
                continue
            if status != "all" and secret_status != status:
                continue
            matching.append((secret, secret_status))

        matching.sort(
            key=lambda item: item[0].name.casefold(),
            reverse=descending,
        )
        filtered_count = len(matching)
        total_pages = (filtered_count + page_size - 1) // page_size
        normalized_index = min(max(0, page_index), max(0, total_pages - 1))
        start = normalized_index * page_size
        selected = matching[start:start + page_size]

        return SecretListPage(
            items=tuple(
                SecretSummary(
                    name=secret.name,
                    note=secret.note or "",
                    expires_on=secret.expires_on,
                    expires_at_time=secret.expires_at_time,
                    allow_cli=secret.allow_cli,
                    status=secret_status,
                )
                for secret, secret_status in selected
            ),
            total_count=len(self._secrets),
            filtered_count=filtered_count,
            status_counts=counts,
            page_index=normalized_index,
        )

    def next_status_transition(
        self,
        *,
        now: datetime | None = None,
    ) -> datetime | None:
        return get_next_expiry_transition(
            (
                (secret.expires_on, secret.expires_at_time)
                for secret in self._secrets
            ),
            now=now,
        )

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
        current.allow_cli = secret.allow_cli
