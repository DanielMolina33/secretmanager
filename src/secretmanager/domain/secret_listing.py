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
    """One bounded page with optional counts for the secrets view."""

    items: tuple[SecretSummary, ...]
    total_count: int | None
    filtered_count: int | None
    status_counts: Mapping[str, int] | None
    page_index: int
