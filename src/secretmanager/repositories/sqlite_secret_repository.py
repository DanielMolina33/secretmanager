from collections.abc import Callable
from datetime import datetime

from sqlalchemy import String, case, cast, func, literal, or_, select
from sqlalchemy.orm import sessionmaker

from ..crypto.secret_encryption import (
    decrypt_secret,
    encrypt_secret,
)
from ..database.models import SecretModel
from ..domain.expiry import (
    EXPIRED,
    EXPIRING,
    VALID,
    get_next_expiry_transition,
)
from ..domain.secret import Secret
from ..domain.secret_listing import SecretListPage, SecretSummary
from .secret_repository import SecretRepository


class SqliteSecretRepository(SecretRepository):
    def __init__(
        self,
        session_factory: sessionmaker,
        encryption_key_provider: Callable[[], bytes],
    ):
        self.session_factory = session_factory
        self.encryption_key_provider = encryption_key_provider

    def save(self, secret: Secret) -> None:
        encryption_key = self.encryption_key_provider()

        value_nonce, encrypted_value = encrypt_secret(
            secret.value,
            encryption_key,
        )

        now = datetime.now()

        model = SecretModel(
            name=secret.name,
            value=encrypted_value,
            value_nonce=value_nonce,
            note=secret.note,
            expires_on=secret.expires_on,
            expires_at_time=secret.expires_at_time,
            allow_cli=secret.allow_cli,
            created_at=now,
            updated_at=now,
        )

        with self.session_factory.begin() as session:
            session.add(model)

    def list(self) -> list[Secret]:
        with self.session_factory() as session:
            statement = select(SecretModel).order_by(SecretModel.name)
            models = session.scalars(statement).all()

            return [self._to_domain(model) for model in models]

    def list_page(
        self,
        *,
        search_text: str = "",
        status: str = "all",
        descending: bool = False,
        page_index: int = 0,
        page_size: int = 25,
        now: datetime | None = None,
    ) -> SecretListPage:
        if page_size < 1:
            raise ValueError("page_size must be greater than zero")
        if status not in {"all", VALID, EXPIRING, EXPIRED}:
            raise ValueError(f"Unknown secret status: {status}")

        current = now or datetime.now()
        status_expression = self._status_expression(current)
        filters = []

        query = search_text.strip().lower()
        if query:
            folded_name = func.secretmanager_lower(
                func.coalesce(SecretModel.name, "")
            )
            folded_note = func.secretmanager_lower(
                func.coalesce(SecretModel.note, "")
            )
            filters.append(
                or_(
                    func.instr(folded_name, query) > 0,
                    func.instr(folded_note, query) > 0,
                )
            )

        if status != "all":
            filters.append(status_expression == status)

        with self.session_factory() as session:
            status_rows = session.execute(
                select(status_expression, func.count(SecretModel.id))
                .group_by(status_expression)
            )
            status_counts = {VALID: 0, EXPIRING: 0, EXPIRED: 0}
            for item_status, count in status_rows:
                status_counts[item_status] = count

            total_count = sum(status_counts.values())
            filtered_count = session.scalar(
                select(func.count(SecretModel.id)).where(*filters)
            ) or 0
            total_pages = (filtered_count + page_size - 1) // page_size
            normalized_index = min(max(0, page_index), max(0, total_pages - 1))

            name_order = SecretModel.name.collate("NOCASE")
            ordering = (
                (name_order.desc(), SecretModel.name.asc())
                if descending
                else (name_order.asc(), SecretModel.name.asc())
            )
            statement = (
                select(
                    SecretModel.name,
                    SecretModel.note,
                    SecretModel.expires_on,
                    SecretModel.expires_at_time,
                    SecretModel.allow_cli,
                    status_expression.label("status"),
                )
                .where(*filters)
                .order_by(*ordering)
                .limit(page_size)
                .offset(normalized_index * page_size)
            )
            rows = session.execute(statement).mappings().all()

        items = tuple(
            SecretSummary(
                name=row["name"],
                note=row["note"] or "",
                expires_on=row["expires_on"],
                expires_at_time=row["expires_at_time"],
                allow_cli=bool(row["allow_cli"]),
                status=row["status"],
            )
            for row in rows
        )
        return SecretListPage(
            items=items,
            total_count=total_count,
            filtered_count=filtered_count,
            status_counts=status_counts,
            page_index=normalized_index,
        )

    def next_status_transition(
        self,
        *,
        now: datetime | None = None,
    ) -> datetime | None:
        with self.session_factory() as session:
            statement = (
                select(SecretModel.expires_on, SecretModel.expires_at_time)
                .where(SecretModel.expires_on.is_not(None))
                .execution_options(yield_per=256)
            )
            rows = session.execute(statement)
            return get_next_expiry_transition(rows, now=now)

    @staticmethod
    def _status_expression(now: datetime):
        date_only_status = case(
            (SecretModel.expires_on > now.date(), VALID),
            (SecretModel.expires_on == now.date(), EXPIRING),
            else_=EXPIRED,
        )
        expiration_value = (
            cast(SecretModel.expires_on, String)
            + literal(" ")
            + cast(SecretModel.expires_at_time, String)
        )
        expiration_datetime = func.datetime(expiration_value)
        warning_start = func.datetime(expiration_datetime, "-5 minutes")
        now_text = now.strftime("%Y-%m-%d %H:%M:%S")

        return case(
            (SecretModel.expires_on.is_(None), VALID),
            (SecretModel.expires_at_time.is_(None), date_only_status),
            (literal(now_text) < warning_start, VALID),
            (literal(now_text) < expiration_datetime, EXPIRING),
            else_=EXPIRED,
        )

    def get(self, name: str) -> Secret | None:
        with self.session_factory() as session:
            statement = select(SecretModel).where(
                SecretModel.name == name
            )

            model = session.scalars(statement).first()

            if model is None:
                return None

            return self._to_domain(model)

    def update(
        self,
        current_name: str,
        secret: Secret,
    ) -> None:
        encryption_key = self.encryption_key_provider()

        value_nonce, encrypted_value = encrypt_secret(
            secret.value,
            encryption_key,
        )

        with self.session_factory.begin() as session:
            statement = select(SecretModel).where(
                SecretModel.name == current_name
            )

            model = session.scalars(statement).first()

            if model is None:
                raise ValueError("Secret not found.")

            model.name = secret.name
            model.value = encrypted_value
            model.value_nonce = value_nonce
            model.note = secret.note
            model.expires_on = secret.expires_on
            model.expires_at_time = secret.expires_at_time
            model.allow_cli = secret.allow_cli
            model.updated_at = datetime.now()

    def delete(self, name: str) -> bool:
        with self.session_factory.begin() as session:
            statement = select(SecretModel).where(
                SecretModel.name == name
            )

            model = session.scalars(statement).first()

            if model is None:
                return False

            session.delete(model)
            return True

    def _to_domain(self, model: SecretModel) -> Secret:
        encryption_key = self.encryption_key_provider()

        value = decrypt_secret(
            model.value,
            model.value_nonce,
            encryption_key,
        )

        return Secret(
            name=model.name,
            value=value,
            note=model.note,
            expires_on=model.expires_on,
            expires_at_time=model.expires_at_time,
            allow_cli=model.allow_cli,
        )
