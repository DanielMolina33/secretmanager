from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest

from sqlcipher3 import dbapi2
from PySide6.QtWidgets import QApplication, QWidget

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secretmanager.database.database import Database
from secretmanager.database.models import SecretModel
from secretmanager.domain.exceptions import SecretNoteTooLongError
from secretmanager.domain.secret import MAX_SECRET_NAME_LENGTH, MAX_SECRET_NOTE_LENGTH
from secretmanager.repositories.memory_secret_repository import InMemorySecretRepository
from secretmanager.services.secret_service import SecretService
from secretmanager.ui.dialogs.secret_dialog import SecretDialog


class SecretNoteLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_service_accepts_limit_and_rejects_longer_notes_on_create_and_update(self):
        service = SecretService(InMemorySecretRepository())
        exact_limit = "n" * MAX_SECRET_NOTE_LENGTH
        created = service.create("NOTE_LIMIT", "value", note=exact_limit)
        self.assertEqual(len(created.note), MAX_SECRET_NOTE_LENGTH)

        with self.assertRaises(SecretNoteTooLongError):
            service.create("NOTE_TOO_LONG", "value", note=exact_limit + "x")

        with self.assertRaises(SecretNoteTooLongError):
            service.update(
                current_name="NOTE_LIMIT",
                name="NOTE_LIMIT",
                value="value",
                note=exact_limit + "x",
            )
        self.assertEqual(service.get("NOTE_LIMIT").note, exact_limit)

    def test_dialog_shows_note_validation_below_note_field(self):
        service = SecretService(InMemorySecretRepository())
        parent = QWidget()
        parent.resize(800, 600)
        dialog = SecretDialog(parent)
        dialog.set_submit_callback(lambda data: service.create(**data))
        self.assertEqual(dialog.name_input.maxLength(), MAX_SECRET_NAME_LENGTH)
        dialog.name_input.setText("NOTE_TOO_LONG")
        dialog.value_input.setText("value")
        dialog.note_input.setPlainText("n" * (MAX_SECRET_NOTE_LENGTH + 1))

        self.assertFalse(dialog.validate())
        self.assertFalse(dialog.note_error.isHidden())
        self.assertIn("100", dialog.note_error.text())
        self.assertIsNone(service.get("NOTE_TOO_LONG"))
        dialog.deleteLater()
        parent.deleteLater()
        self.app.processEvents()

    def test_database_rejects_note_above_limit(self):
        with tempfile.TemporaryDirectory(prefix="secret-note-limit-") as directory:
            database = Database(Path(directory) / "vault.db", b"n" * 32)
            database.create_tables()
            now = datetime.now()
            try:
                with self.assertRaises(dbapi2.IntegrityError):
                    with database.Session.begin() as session:
                        session.add(SecretModel(
                            name="NOTE_TOO_LONG",
                            value=b"ciphertext",
                            value_nonce=b"v" * 12,
                            note="n" * (MAX_SECRET_NOTE_LENGTH + 1),
                            expires_on=None,
                            expires_at_time=None,
                            allow_cli=False,
                            created_at=now,
                            updated_at=now,
                        ))
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
