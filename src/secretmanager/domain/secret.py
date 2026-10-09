from dataclasses import dataclass
from datetime import date, time

MAX_SECRET_NAME_LENGTH = 100
MAX_SECRET_NOTE_LENGTH = 100

@dataclass
class Secret:
    name: str
    value: str
    note: str = ""
    expires_on: date | None = None
    expires_at_time: time | None = None
    allow_cli: bool = False