from dataclasses import dataclass
from datetime import date, time

@dataclass
class Secret:
    name: str
    value: str
    note: str = ""
    expires_on: date | None = None
    expires_at_time: time | None = None