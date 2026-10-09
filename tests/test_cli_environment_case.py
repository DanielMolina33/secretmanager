from __future__ import annotations

import contextlib
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from sqlcipher3 import dbapi2
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secretmanager import cli
from secretmanager.database.database import Database
from secretmanager.database.models import SecretModel
from secretmanager.domain.exceptions import DuplicateSecretError, InvalidSecretNameError
from secretmanager.domain.secret import MAX_SECRET_NAME_LENGTH, Secret
from secretmanager.repositories.memory_secret_repository import InMemorySecretRepository
from secretmanager.ipc import LocalSecretServer
from secretmanager.repositories.sqlite_secret_repository import SqliteSecretRepository
from secretmanager.services.secret_service import SecretService


class SecretNameUppercaseTests(unittest.TestCase):
    def _create_database(self, data_dir: Path, key: bytes):
        database = Database(data_dir / "vault.db", key)
        database.create_tables()
        service = SecretService(
            SqliteSecretRepository(database.Session, lambda: key)
        )
        return database, service

    def test_service_stores_names_uppercase_and_rejects_case_collisions(self):
        with tempfile.TemporaryDirectory(prefix="secret-name-case-") as directory:
            data_dir = Path(directory)
            key = b"c" * 32
            database, service = self._create_database(data_dir, key)
            try:
                created = service.create(
                    "SM_CASE_SECRET", "UPPER_SECRET_VALUE", allow_cli=True
                )
                self.assertEqual(created.name, "SM_CASE_SECRET")

                with self.assertRaises(InvalidSecretNameError):
                    service.create("Sm_Case_Secret", "mixed-case")
                with self.assertRaises(DuplicateSecretError):
                    service.create("SM_CASE_SECRET", "duplicate")

                with self.assertRaises(InvalidSecretNameError):
                    service.update(
                        current_name="SM_CASE_SECRET",
                        name="sm_case_secret",
                        value="invalid-update",
                    )

                updated = service.update(
                    current_name="SM_CASE_SECRET",
                    name="SM_CASE_SECRET",
                    value="updated-value",
                )
                self.assertEqual(updated.name, "SM_CASE_SECRET")
                self.assertEqual(service.get("SM_CASE_SECRET").value, "updated-value")

                with database.Session() as session:
                    stored_name = session.scalar(select(SecretModel.name))
                self.assertEqual(stored_name, "SM_CASE_SECRET")
            finally:
                database.close()

    def test_service_limits_names_to_100_characters(self):
        service = SecretService(InMemorySecretRepository())
        accepted_name = "A" * MAX_SECRET_NAME_LENGTH
        created = service.create(accepted_name, "value")
        self.assertEqual(created.name, accepted_name)

        with self.assertRaises(InvalidSecretNameError):
            service.create("A" * (MAX_SECRET_NAME_LENGTH + 1), "value")

    def test_legacy_lowercase_name_blocks_case_collision_and_can_be_renamed(self):
        repository = InMemorySecretRepository()
        repository.save(Secret(name="legacy_secret", value="old-value"))
        service = SecretService(repository)

        with self.assertRaises(DuplicateSecretError):
            service.create("LEGACY_SECRET", "duplicate")

        updated = service.update(
            current_name="legacy_secret",
            name="LEGACY_SECRET",
            value="updated-value",
        )
        self.assertEqual(updated.name, "LEGACY_SECRET")
        self.assertIsNone(repository.get("legacy_secret"))
        self.assertEqual(repository.get("LEGACY_SECRET").value, "updated-value")

    def test_database_rejects_direct_lowercase_names(self):
        with tempfile.TemporaryDirectory(prefix="secret-name-check-") as directory:
            database = Database(Path(directory) / "vault.db", b"d" * 32)
            database.create_tables()
            now = datetime.now()
            try:
                with self.assertRaises(dbapi2.IntegrityError):
                    with database.Session.begin() as session:
                        session.add(SecretModel(
                            name="lowercase_secret",
                            value=b"ciphertext",
                            value_nonce=b"n" * 12,
                            note="",
                            expires_on=None,
                            expires_at_time=None,
                            allow_cli=False,
                            created_at=now,
                            updated_at=now,
                        ))
            finally:
                database.close()

    def test_database_rejects_names_above_100_characters(self):
        with tempfile.TemporaryDirectory(prefix="secret-name-length-") as directory:
            database = Database(Path(directory) / "vault.db", b"l" * 32)
            database.create_tables()
            now = datetime.now()
            try:
                with self.assertRaises(dbapi2.IntegrityError):
                    with database.Session.begin() as session:
                        session.add(SecretModel(
                            name="A" * (MAX_SECRET_NAME_LENGTH + 1),
                            value=b"ciphertext",
                            value_nonce=b"n" * 12,
                            note="",
                            expires_on=None,
                            expires_at_time=None,
                            allow_cli=False,
                            created_at=now,
                            updated_at=now,
                        ))
            finally:
                database.close()

    def test_cli_normalizes_requested_name_and_injects_uppercase_environment_key(self):
        with tempfile.TemporaryDirectory(prefix="cli-env-case-") as directory:
            data_dir = Path(directory)
            (data_dir / "config.json").write_text(
                json.dumps({"SecretManager": {"CliIntegrationEnabled": True}}),
                encoding="utf-8",
            )
            key = b"e" * 32
            database, service = self._create_database(data_dir, key)
            service.create("SM_CASE_SECRET", "CLI_SECRET_VALUE", allow_cli=True)
            server = LocalSecretServer(data_dir, service.get)
            server.start()
            try:
                expected = hashlib.sha256(b"CLI_SECRET_VALUE").hexdigest()
                child_code = (
                    "import hashlib,os,sys; "
                    "value=os.getenv('SM_CASE_SECRET',''); "
                    "sys.exit(0 if hashlib.sha256(value.encode()).hexdigest()==sys.argv[1] else 17)"
                )
                with patch.object(cli, "get_data_dir", return_value=data_dir):
                    result = cli.main([
                        "--use",
                        "sm_case_secret",
                        "--",
                        sys.executable,
                        "-c",
                        child_code,
                        expected,
                    ])
                self.assertEqual(result, 0)
            finally:
                server.close()
                database.close()

    def test_cli_rejects_requested_names_that_normalize_to_a_duplicate(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            result = cli.main([
                "--use",
                "SM_CASE_SECRET",
                "sm_case_secret",
                "--",
                sys.executable,
                "-c",
                "pass",
            ])
        self.assertEqual(result, 2)
        self.assertIn("must be unique", output.getvalue())


if __name__ == "__main__":
    unittest.main()
