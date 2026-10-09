from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secretmanager.domain.expiry import (
    EXPIRED,
    EXPIRING,
    VALID,
    get_expiry_status,
    get_next_expiry_transition,
)
from secretmanager.services.secret_service import SecretService


class ExpiryRuleBoundaryTests(unittest.TestCase):
    def test_date_only_secret_changes_state_at_local_midnight_boundaries(self):
        expiry_date = date(2032, 4, 10)
        self.assertEqual(
            get_expiry_status(
                expiry_date, None,
                now=datetime(2032, 4, 9, 23, 59, 59),
            ),
            VALID,
        )
        self.assertEqual(
            get_expiry_status(
                expiry_date, None,
                now=datetime(2032, 4, 10, 0, 0),
            ),
            EXPIRING,
        )
        self.assertEqual(
            get_expiry_status(
                expiry_date, None,
                now=datetime(2032, 4, 11, 0, 0),
            ),
            EXPIRED,
        )

    def test_timed_secret_has_exact_five_minute_warning_window(self):
        expiry_date = date(2032, 4, 10)
        expiry_time = time(12, 0)
        self.assertEqual(
            get_expiry_status(
                expiry_date, expiry_time,
                now=datetime(2032, 4, 10, 11, 54, 59),
            ),
            VALID,
        )
        self.assertEqual(
            get_expiry_status(
                expiry_date, expiry_time,
                now=datetime(2032, 4, 10, 11, 55),
            ),
            EXPIRING,
        )
        self.assertEqual(
            get_expiry_status(
                expiry_date, expiry_time,
                now=datetime(2032, 4, 10, 11, 59, 59),
            ),
            EXPIRING,
        )
        self.assertEqual(
            get_expiry_status(
                expiry_date, expiry_time,
                now=datetime(2032, 4, 10, 12, 0),
            ),
            EXPIRED,
        )

    def test_midnight_is_a_valid_expiry_time_with_the_same_grace_rule(self):
        expiry_date = date(2032, 4, 10)
        self.assertEqual(
            get_expiry_status(
                expiry_date, time.min,
                now=datetime(2032, 4, 9, 23, 54, 59),
            ),
            VALID,
        )
        self.assertEqual(
            get_expiry_status(
                expiry_date, time.min,
                now=datetime(2032, 4, 9, 23, 55),
            ),
            EXPIRING,
        )
        self.assertEqual(
            get_expiry_status(
                expiry_date, time.min,
                now=datetime(2032, 4, 10, 0, 0),
            ),
            EXPIRED,
        )

    def test_no_expiry_is_always_valid(self):
        self.assertEqual(
            get_expiry_status(None, time(9, 30), now=datetime(2032, 1, 1)),
            VALID,
        )

    def test_next_transition_returns_only_the_earliest_future_boundary(self):
        now = datetime(2032, 4, 10, 11, 54)
        expiries = [
            (date(2032, 4, 10), time(12, 0)),
            (date(2032, 4, 10), time(12, 10)),
            (date(2032, 4, 9), time(10, 0)),
            (None, None),
        ]
        self.assertEqual(
            get_next_expiry_transition(expiries, now=now),
            datetime(2032, 4, 10, 11, 55),
        )

    def test_transition_at_current_instant_is_not_reported_again(self):
        now = datetime(2032, 4, 10, 11, 55)
        self.assertEqual(
            get_next_expiry_transition(
                [(date(2032, 4, 10), time(12, 0))],
                now=now,
            ),
            datetime(2032, 4, 10, 12, 0),
        )
        self.assertIsNone(
            get_next_expiry_transition(
                [(date(2032, 4, 10), time(12, 0))],
                now=datetime(2032, 4, 10, 12, 0),
            )
        )

    def test_service_rejects_time_without_date_and_normalizes_seconds(self):
        repository = Mock()
        repository.get.return_value = None
        repository.name_exists_case_insensitive.return_value = False
        service = SecretService(repository)

        with self.assertRaisesRegex(ValueError, "requires an expiry date"):
            service.create(
                "NO_DATE",
                "value",
                expires_at_time=time(8, 15, 59),
            )
        repository.save.assert_not_called()

        created = service.create(
            "WITH_DATE",
            "value",
            expires_on=date(2032, 4, 10),
            expires_at_time=time(8, 15, 59),
        )
        self.assertEqual(created.expires_at_time, time(8, 15))
        repository.save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
