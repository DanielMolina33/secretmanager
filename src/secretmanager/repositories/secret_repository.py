from abc import ABC, abstractmethod

from ..domain.secret import Secret


class SecretRepository(ABC):
    @abstractmethod
    def save(self, secret: Secret) -> None:
        pass

    @abstractmethod
    def list(self) -> list[Secret]:
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