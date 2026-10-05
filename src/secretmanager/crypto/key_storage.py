import os
import tempfile
from pathlib import Path

from .key_envelope import KeyEnvelope


class KeyStorage:
    def __init__(self, path: Path):
        self.path = path

    def save(self, envelope: KeyEnvelope) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as file:
                file.write(envelope.to_bytes())
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.path)
        except Exception:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    def load(self) -> KeyEnvelope:
        if not self.path.exists():
            raise FileNotFoundError(f"Key file not found: {self.path}")
        return KeyEnvelope.from_bytes(self.path.read_bytes())
