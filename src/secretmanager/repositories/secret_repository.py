from abc import ABC, abstractmethod
from datetime import datetime

from ..domain.secret import Secret
from ..domain.secret_listing import SecretListPage


class SecretRepository(ABC):
    @abstractmethod
    def save(self, secret: Secret) -> None:
        pass

    @abstractmethod
    def list(self) -> list[Secret]:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def next_status_transition(
        self,
        *,
        now: datetime | None = None,
    ) -> datetime | None:
        pass

    @abstractmethod
    def get(self, name: str) -> Secret | None:
        pass

    @abstractmethod
    def delete(self, name: str) -> bool:
        pass

    @abstractmethod
    def update(
        self,
        current_name: str,
        secret: Secret,
    ) -> None:
        pass
