"""Shared, time-sensitive secret expiry rules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta


VALID = "Vigente"
EXPIRING = "Por vencer"
EXPIRED = "Vencido"


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
