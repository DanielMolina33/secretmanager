from dataclasses import dataclass
from datetime import date, time
from typing import Mapping


@dataclass(frozen=True)
class SecretSummary:
    """Non-sensitive fields needed to render one secret in the list."""

    name: str
    note: str
    expires_on: date | None
    expires_at_time: time | None
    allow_cli: bool
    status: str


@dataclass(frozen=True)
class SecretListPage:
    """One bounded page plus counts used by the secrets view."""

    items: tuple[SecretSummary, ...]
    total_count: int
    filtered_count: int
    status_counts: Mapping[str, int]
    page_index: int
