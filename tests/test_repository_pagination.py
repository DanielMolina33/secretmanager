from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqlcipher3 import dbapi2
from secretmanager.database.database import Database
from secretmanager.domain.expiry import EXPIRED, EXPIRING, VALID
from secretmanager.repositories.sqlite_secret_repository import SqliteSecretRepository
from secretmanager.services.secret_service import SecretService


class RepositoryPaginationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="repository-pages-")
        self.root = Path(self.temp_dir.name)
        self.key = b"p" * 32
        self.database = Database(self.root / "vault.db", self.key)
        self.database.create_tables()
        self.repository = SqliteSecretRepository(
            self.database.Session,
            lambda: self.key,
        )
        self.service = SecretService(self.repository)

    def tearDown(self):
        self.database.close()
        self.temp_dir.cleanup()

    def test_pages_are_bounded_sorted_and_clamped_to_last_result_page(self):
        for index in range(53):
            self.service.create(
                f"ITEM_{index:03}",
                f"value-{index}",
                note="ordinary note",
            )

        first = self.service.list_page(page_index=0, page_size=25)
        second = self.service.list_page(page_index=1, page_size=25)
        last = self.service.list_page(page_index=100, page_size=25)

        self.assertEqual(first.filtered_count, 53)
        self.assertEqual(first.page_index, 0)
        self.assertEqual(len(first.items), 25)
        self.assertEqual([item.name for item in first.items],
                         [f"ITEM_{index:03}" for index in range(25)])
        self.assertEqual(len(second.items), 25)
        self.assertEqual([item.name for item in second.items],
                         [f"ITEM_{index:03}" for index in range(25, 50)])
        self.assertEqual(last.page_index, 2)
        self.assertEqual([item.name for item in last.items],
                         ["ITEM_050", "ITEM_051", "ITEM_052"])
        self.assertFalse(hasattr(first.items[0], "value"))

    def test_status_counts_and_status_filter_use_the_same_clock(self):
        now = datetime(2032, 4, 10, 12, 0)
        self.service.create("DATE_VALID", "v", expires_on=date(2032, 4, 11))
        self.service.create("DATE_EXPIRING", "e", expires_on=date(2032, 4, 10))
        self.service.create(
            "TIME_EXPIRING",
            "e",
            expires_on=date(2032, 4, 10),
            expires_at_time=time(12, 4),
        )
        self.service.create("DATE_EXPIRED", "x", expires_on=date(2032, 4, 9))

        page = self.service.list_page(page_size=10, now=now)
        self.assertEqual(
            page.status_counts,
            {VALID: 1, EXPIRING: 2, EXPIRED: 1},
        )
        self.assertEqual(page.total_count, 4)
        expiring = self.service.list_page(
            status=EXPIRING,
            page_size=10,
            now=now,
        )
        self.assertEqual(
            [item.name for item in expiring.items],
            ["DATE_EXPIRING", "TIME_EXPIRING"],
        )
        self.assertEqual(expiring.filtered_count, 2)

    def test_search_treats_sql_wildcards_as_literal_text(self):
        self.service.create("MATCH_LITERAL", "v", note="contains 100%_literal token")
        self.service.create("MATCH_OTHER", "v", note="contains 100XXliteral token")
        page = self.service.list_page(search_text="100%_literal", page_size=25)
        self.assertEqual([item.name for item in page.items], ["MATCH_LITERAL"])
        self.assertEqual(page.filtered_count, 1)

    def test_search_is_case_insensitive_for_unicode_and_note_fields(self):
        self.service.create("UNICODE_NOTE", "v", note="Llave ÁRBOL")
        page = self.service.list_page(search_text="árbol")
        self.assertEqual([item.name for item in page.items], ["UNICODE_NOTE"])

    def test_descending_order_and_zero_result_page_are_deterministic(self):
        for name in ("ALPHA", "BETA", "GAMMA"):
            self.service.create(name, "v")
        ascending = self.service.list_page(page_size=10)
        descending = self.service.list_page(page_size=10, descending=True)
        self.assertEqual([item.name for item in ascending.items],
                         ["ALPHA", "BETA", "GAMMA"])
        self.assertEqual([item.name for item in descending.items],
                         ["GAMMA", "BETA", "ALPHA"])

        empty = self.service.list_page(search_text="no-match", page_size=25)
        self.assertEqual(empty.items, ())
        self.assertEqual(empty.filtered_count, 0)
        self.assertEqual(empty.page_index, 0)

    def test_optional_aggregates_are_not_returned_when_skipped(self):
        self.service.create("ONE_SECRET", "v")
        page = self.service.list_page(
            include_status_counts=False,
            include_filtered_count=False,
        )
        self.assertIsNone(page.status_counts)
        self.assertIsNone(page.total_count)
        self.assertIsNone(page.filtered_count)
        self.assertEqual([item.name for item in page.items], ["ONE_SECRET"])

    def test_invalid_page_size_and_status_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "page_size"):
            self.service.list_page(page_size=0)
        with self.assertRaisesRegex(ValueError, "Unknown secret status"):
            self.service.list_page(status="unknown")

    def test_database_rejects_time_without_expiry_date(self):
        with self.assertRaises(dbapi2.IntegrityError):
            with self.database.engine.begin() as connection:
                connection.exec_driver_sql(
                    "INSERT INTO secrets "
                    "(name, value, value_nonce, note, expires_on, expires_at_time, "
                    "allow_cli, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "INVALID_DB_ROW",
                        b"ciphertext",
                        b"nonce",
                        "",
                        None,
                        "12:00:00",
                        0,
                        "2032-04-10 12:00:00",
                        "2032-04-10 12:00:00",
                    ),
                )


if __name__ == "__main__":
    unittest.main()


