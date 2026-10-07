from pathlib import Path
import threading

from sqlalchemy import create_engine, event
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
        self._connection_lock = threading.Lock()
        self._active_connections: set[object] = set()
        self._closed = False

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.engine = self._create_engine()
        event.listen(self.engine, "connect", self._track_connection)
        event.listen(self.engine, "close", self._forget_connection)
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
            connection.create_function(
                "secretmanager_lower",
                1,
                lambda value: value.lower() if value is not None else "",
            )

            return connection

        return create_engine(
            "sqlite://",
            creator=create_connection,
            poolclass=NullPool,
        )

    def _track_connection(self, connection, _record) -> None:
        with self._connection_lock:
            if not self._closed:
                self._active_connections.add(connection)
                return

        # A worker may race with vault locking and finish opening a connection
        # after close() has begun. Reject that connection before any query runs.
        connection.close()
        raise RuntimeError("The encrypted database is closed.")

    def _forget_connection(self, connection, _record) -> None:
        with self._connection_lock:
            self._active_connections.discard(connection)

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        with self._connection_lock:
            if self._closed:
                return
            self._closed = True
            active_connections = tuple(self._active_connections)

        # sqlite3 documents interrupt() as safe to call from another thread;
        # it aborts an executing statement with OperationalError.
        for connection in active_connections:
            try:
                connection.interrupt()
            except Exception:
                pass

        self.engine.dispose()
