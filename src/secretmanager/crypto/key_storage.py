from pathlib import Path

from .key_envelope import KeyEnvelope


class KeyStorage:
    def __init__(self, path: Path):
        self.path = path

    def save(self, envelope: KeyEnvelope) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.path.write_bytes(
            envelope.to_bytes()
        )

    def load(self) -> KeyEnvelope:
        if not self.path.exists():
            raise FileNotFoundError(
                f"Key file not found: {self.path}"
            )

        return KeyEnvelope.from_bytes(
            self.path.read_bytes()
        )