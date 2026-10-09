from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Integer, LargeBinary, String, Text, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..domain.secret import MAX_SECRET_NAME_LENGTH, MAX_SECRET_NOTE_LENGTH


class Base(DeclarativeBase):
    pass


class SecretModel(Base):
    __tablename__ = "secrets"
    __table_args__ = (
        CheckConstraint(
            f"length(name) <= {MAX_SECRET_NAME_LENGTH}",
            name="ck_secrets_name_max_length",
        ),
        CheckConstraint(
            f"length(note) <= {MAX_SECRET_NOTE_LENGTH}",
            name="ck_secrets_note_max_length",
        ),
        CheckConstraint(
            "name = upper(name)",
            name="ck_secrets_name_uppercase",
        ),
        CheckConstraint(
            "expires_at_time IS NULL OR expires_on IS NOT NULL",
            name="ck_secrets_expiry_time_requires_date",
        ),
        CheckConstraint(
            "allow_cli IN (0, 1)",
            name="ck_secrets_allow_cli_boolean",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(MAX_SECRET_NAME_LENGTH),
        unique=True,
        nullable=False,
    )

    value: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    value_nonce: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    expires_on: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    expires_at_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    allow_cli: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )