"""Shared, time-sensitive secret expiry rules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta


VALID = "valid"
EXPIRING = "expiring"
EXPIRED = "expired"


def get_expiry_status(
    expires_on: date | None,
    expires_at_time: time | None,
    *,
    now: datetime | None = None,
) -> str:
    """Return the current status using the same rules for the UI and CLI."""
    if expires_on is None:
        return VALID

    current = now or datetime.now()
    if expires_at_time is None:
        if current.date() < expires_on:
            return VALID
        if current.date() == expires_on:
            return EXPIRING
        return EXPIRED

    expires_at = datetime.combine(expires_on, expires_at_time)
    warning_starts_at = expires_at - timedelta(minutes=5)
    if current < warning_starts_at:
        return VALID
    if current < expires_at:
        return EXPIRING
    return EXPIRED


def get_next_expiry_transition(
    expiries: Iterable[tuple[date | None, time | None]],
    *,
    now: datetime | None = None,
) -> datetime | None:
    """Find the next state boundary without retaining the input rows."""
    current = now or datetime.now()
    next_transition = None

    for expires_on, expires_at_time in expiries:
        if expires_on is None:
            continue

        if expires_at_time is None:
            candidates = (
                datetime.combine(expires_on, time.min),
                datetime.combine(expires_on + timedelta(days=1), time.min),
            )
        else:
            expires_at = datetime.combine(expires_on, expires_at_time)
            candidates = (
                expires_at - timedelta(minutes=5),
                expires_at,
            )

        for candidate in candidates:
            if candidate > current and (
                next_transition is None or candidate < next_transition
            ):
                next_transition = candidate

    return next_transition
