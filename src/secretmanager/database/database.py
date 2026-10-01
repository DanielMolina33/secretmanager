from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from sqlcipher3 import dbapi2

from .models import Base


class Database:
    def __init__(
        self,
        path: Path,
        key: bytes,
    ):
        self.path = path
        self.key = key

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.engine = self._create_engine()
        self.Session = sessionmaker(
            bind=self.engine,
        )

    def _create_engine(self) -> Engine:
        key_hex = self.key.hex()

        def create_connection():
            connection = dbapi2.connect(
                str(self.path),
            )

            connection.execute(
                f"PRAGMA key = \"x'{key_hex}'\""
            )

            return connection

        return create_engine(
            "sqlite://",
            creator=create_connection,
            poolclass=NullPool,
        )

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()