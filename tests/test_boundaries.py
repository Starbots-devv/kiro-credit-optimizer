import copy
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path

from starbots_kco.config import Config, CreditError
from starbots_kco.estimates import estimate
from starbots_kco.ledger import Ledger
from starbots_kco.reporting import budget_status, report


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config.create("synthetic", "2000", "1000", "100", 1)
        self.path = Path(self.temp.name) / "ledger.sqlite3"
        self.ledger = Ledger(self.path, self.config, create=True)
        self.addCleanup(self.ledger.close)

    def snap(self, balance, at, source="manual-official"):
        return self.ledger.snapshot(balance, at, source, "synthetic fixture")

    def test_threshold_boundaries_and_zero_allocations(self):
        for usage, expected in (
            ("49.999999", "normal"),
            ("50", "information"),
            ("75", "caution"),
            ("90", "high-usage"),
            ("101", "high-usage"),
        ):
            with self.subTest(usage=usage):
                self.assertEqual(budget_status("100", usage, [50, 75, 90])["alert"], expected)
        self.assertEqual(budget_status("0", "1", [50, 75, 90])["alert"], "unallocated")
        self.assertEqual(budget_status("100", "101", [50, 75, 90])["remaining"], "-1")

    def test_mixed_provenance_is_preserved(self):
        a = self.snap("1800", "2026-01-02T12:00:00Z", "official-report")
        b = self.snap("1750", "2026-01-03T12:00:00Z", "authorized-local")
        self.ledger.claim(a, b, exclusive=True)
        claim = self.ledger.claims()[0]
        self.assertEqual(
            (claim["start_source"], claim["end_source"]), ("official-report", "authorized-local")
        )
        self.assertEqual(claim["start_reference"], "synthetic fixture")

    def test_short_observation_window_has_no_projection(self):
        self.snap("1800", "2026-01-02T12:00:00Z")
        self.snap("1750", "2026-01-02T13:00:00Z")
        self.assertIsNone(
            report(self.config, self.ledger, date(2026, 1, 3))["projection"]["cycle_usage"]
        )

    def test_balance_increase_is_partial_and_disables_projection(self):
        self.snap("1800", "2026-01-02T12:00:00Z")
        self.snap("1900", "2026-01-03T12:00:00Z")
        self.snap("1850", "2026-01-04T12:00:00Z")
        data = report(self.config, self.ledger, date(2026, 1, 5))
        self.assertEqual(data["account"]["observed_interval_usage"], "50")
        self.assertTrue(data["account"]["adjustments_excluded"])
        self.assertIsNone(data["projection"]["cycle_usage"])

    def test_budget_context_must_agree(self):
        self.config.data["tasks"]["fix"] = {
            "budget": "100",
            "phase": "implementation",
            "task_type": "bugfix",
            "complexity": "small",
            "size": "medium",
            "strategy": "balanced",
            "testing": "targeted",
        }
        self.config.validate()
        with self.assertRaises(CreditError):
            self.ledger.snapshot(
                "1800",
                "2026-01-02T12:00:00Z",
                "manual-official",
                "synthetic",
                task="fix",
                phase="review",
            )

    def test_unverified_history_does_not_calibrate_estimate(self):
        for day in (2, 4, 6):
            a = self.snap("1800", f"2026-01-{day:02d}T12:00:00Z")
            b = self.snap("1750", f"2026-01-{day + 1:02d}T12:00:00Z")
            self.ledger.claim(a, b, exclusive=True)
        self.assertEqual(estimate(self.config, self.ledger)["sample_count"], 0)

    def test_invalid_estimate_arguments(self):
        for args in (
            {"phases": 0},
            {"retries": -1},
            {"uncertainty": "2"},
            {"task_type": "unknown"},
        ):
            with self.subTest(args=args), self.assertRaises(CreditError):
                estimate(self.config, self.ledger, **args)

    def test_malformed_configuration_context_fails_with_credit_error(self):
        self.config.data["tasks"]["bad"] = {
            "budget": "1",
            "phase": [],
            "task_type": "feature",
            "complexity": "medium",
            "size": "medium",
            "strategy": "balanced",
            "testing": "targeted",
        }
        with self.assertRaises(CreditError):
            self.config.validate()

    def test_ledger_identity_and_unknown_schema_are_not_reset(self):
        other = Config(copy.deepcopy(self.config.data))
        other.data["renewal_day"] = 2
        with self.assertRaises(CreditError):
            Ledger(self.path, other)
        future_path = Path(self.temp.name) / "future.sqlite3"
        with closing(sqlite3.connect(future_path)) as db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaises(CreditError):
            Ledger(future_path, self.config)
        with closing(sqlite3.connect(future_path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_second_connection_sees_duplicate_and_overlap(self):
        a = self.snap("1800", "2026-01-02T12:00:00Z")
        b = self.snap("1750", "2026-01-03T12:00:00Z")
        second = Ledger(self.path, self.config)
        self.addCleanup(second.close)
        self.ledger.claim(a, b, exclusive=True)
        with self.assertRaises(CreditError):
            second.claim(a, b, exclusive=True)
        with self.assertRaises(CreditError):
            second.snapshot("1800", "2026-01-02T12:00:00Z", "manual-official", "synthetic")


if __name__ == "__main__":
    unittest.main()
