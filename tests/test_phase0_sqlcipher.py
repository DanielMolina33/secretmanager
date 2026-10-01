from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from sqlalchemy import text
from sqlcipher3 import dbapi2

from secretmanager.database.database import Database
from secretmanager.database.models import SecretModel


class PhaseZeroSqlCipherTests(unittest.TestCase):
    def test_database_is_encrypted_and_wrong_key_cannot_read_it(self):
        marker = "PHASE0_SQLCIPHER_PLAINTEXT_MARKER"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.db"
            key = bytes(range(32))
            database = Database(path, key)
            database.create_tables()
            now = datetime.now()
            with database.Session.begin() as session:
                session.add(SecretModel(
                    name="PHASE0_PROBE",
                    value=b"ciphertext-value",
                    value_nonce=b"n" * 12,
                    note=marker,
                    expires_on=None,
                    expires_at_time=None,
                    created_at=now,
                    updated_at=now,
                ))
            with database.Session() as session:
                self.assertEqual(session.execute(
                    text("SELECT note FROM secrets")
                ).scalar_one(), marker)
            database.close()

            self.assertNotIn(marker.encode("utf-8"), path.read_bytes())
            wrong_key_database = Database(path, b"x" * 32)
            try:
                with self.assertRaises(dbapi2.DatabaseError):
                    with wrong_key_database.Session() as session:
                        session.execute(text("SELECT * FROM secrets")).all()
            finally:
                wrong_key_database.close()


if __name__ == "__main__":
    unittest.main()
