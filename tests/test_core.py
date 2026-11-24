import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from starbots_kco.config import Config, CreditError, credits, cycle, load_config
from starbots_kco.estimates import estimate
from starbots_kco.ledger import Ledger
from starbots_kco.reporting import report


class ConfigTests(unittest.TestCase):
    def test_credit_values_are_exact(self):
        self.assertEqual(credits("0.123456"), 123456)
        self.assertEqual(credits("2000"), 2000000000)

    def test_invalid_credit_values(self):
        for value in (
            "-1",
            "NaN",
            "Infinity",
            "0.0000001",
            True,
            "bad",
            "1e100",
            "1.000000000000000000000000000001",
            "1e-10000000",
        ):
            with self.subTest(value=value), self.assertRaises(CreditError):
                credits(value)

    def test_month_end_and_leap_year(self):
        self.assertEqual(cycle(date(2024, 2, 29), 31), (date(2024, 2, 29), date(2024, 3, 31)))
        self.assertEqual(cycle(date(2025, 2, 27), 31), (date(2025, 1, 31), date(2025, 2, 28)))
        self.assertEqual(cycle(date(2026, 1, 1), 1), (date(2026, 1, 1), date(2026, 2, 1)))

    def test_defaults_preserve_reserve(self):
        config = Config.create("synthetic", "2000", "1000", "100", 1)
        self.assertEqual(sum(credits(v) for v in config.data["phases"].values()), credits("900"))

    def test_configuration_rejects_overallocation(self):
        config = Config.create("synthetic", "2000", "1000", "100", 1)
        for key, value in (("reserve", "1001"), ("project_budget", "3000"), ("renewal_day", 0)):
            bad = dict(config.data, **{key: value})
            with self.subTest(key=key), self.assertRaises(CreditError):
                Config(bad)

    def test_invalid_thresholds(self):
        config = Config.create("synthetic", "2000", "1000", "100", 1)
        for thresholds in ([75, 50, 90], [0, 75, 90], [50, 50, 90], [50, 75, 101]):
            with self.subTest(thresholds=thresholds), self.assertRaises(CreditError):
                Config(dict(config.data, thresholds=thresholds))

    def test_corrupt_configuration_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "config.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(CreditError):
                load_config(path)
            self.assertEqual(path.read_text(), "{broken")


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config.create("synthetic", "2000", "1000", "100", 1)
        self.ledger = Ledger(Path(self.temp.name) / "usage.sqlite3", self.config, create=True)
        self.addCleanup(self.ledger.close)

    def snap(self, balance, day, **kwargs):
        return self.ledger.snapshot(
            balance,
            f"2026-01-{day:02d}T12:00:00Z",
            "manual-official",
            "synthetic fixture",
            **kwargs,
        )

    def test_snapshot_retains_provenance_and_context(self):
        sid = self.snap("1800.25", 2, note="synthetic", phase="implementation")
        row = self.ledger.snapshots()[0]
        self.assertEqual(row["id"], sid)
        self.assertEqual(row["balance"], "1800.25")
        self.assertEqual(row["source"], "manual-official")
        self.assertEqual(row["project"], "synthetic")
        self.assertEqual(row["phase"], "implementation")

    def test_duplicate_equivalent_timestamp_rejected(self):
        self.snap("1800", 2)
        with self.assertRaises(CreditError):
            self.ledger.snapshot(
                "1800", "2026-01-02T06:00:00-06:00", "manual-official", "synthetic"
            )
        self.assertEqual(len(self.ledger.snapshots()), 1)

    def test_invalid_date_balance_or_source_rejected(self):
        for balance, timestamp, source in (
            ("-1", "2026-01-02T12:00:00Z", "manual-official"),
            ("2", "yesterday", "manual-official"),
            ("2", "2026-01-02T12:00:00", "manual-official"),
            ("2", "2026-01-02T12:00:00Z", "guess"),
        ):
            with self.subTest(source=source, timestamp=timestamp), self.assertRaises(CreditError):
                self.ledger.snapshot(balance, timestamp, source, "synthetic")

    def test_account_difference_is_not_project_usage(self):
        self.snap("1800", 2)
        self.snap("1700", 3)
        data = report(self.config, self.ledger, date(2026, 1, 4))
        self.assertEqual(data["account"]["observed_interval_usage"], "100")
        self.assertEqual(data["project"]["attributed_usage"], "0")
        self.assertEqual(data["account"]["latest_balance"], "1700")

    def test_claim_needs_explicit_exclusivity(self):
        a, b = self.snap("1800", 2), self.snap("1700", 3)
        with self.assertRaises(CreditError):
            self.ledger.claim(a, b, exclusive=False)

    def test_claim_rejects_duplicate_and_overlap(self):
        a, b, c = self.snap("1800", 2), self.snap("1700", 3), self.snap("1600", 4)
        self.ledger.claim(a, b, exclusive=True, phase="implementation", verified=True)
        for start, end in ((a, b), (a, c)):
            with self.subTest(start=start, end=end), self.assertRaises(CreditError):
                self.ledger.claim(start, end, exclusive=True)
        self.ledger.claim(b, c, exclusive=True)

    def test_renewal_boundary_not_subtracted(self):
        a = self.snap("100", 31)
        b = self.ledger.snapshot("1900", "2026-02-01T12:00:00Z", "manual-official", "synthetic")
        with self.assertRaises(CreditError):
            self.ledger.claim(a, b, exclusive=True)
        self.assertEqual(
            report(self.config, self.ledger, date(2026, 2, 2))["account"][
                "observed_interval_usage"
            ],
            "0",
        )

    def test_increase_inside_claim_rejected(self):
        a = self.snap("1800", 2)
        self.snap("1900", 3)
        b = self.snap("1700", 4)
        with self.assertRaises(CreditError):
            self.ledger.claim(a, b, exclusive=True)

    def test_backfill_cannot_invalidate_claim(self):
        a, b = self.snap("1800", 2), self.snap("1700", 4)
        self.ledger.claim(a, b, exclusive=True)
        with self.assertRaises(CreditError):
            self.snap("1900", 3)
        self.assertEqual(len(self.ledger.snapshots()), 2)

    def test_alerts_use_spendable_budget(self):
        a, b = self.snap("1800", 2), self.snap("970", 3)
        self.ledger.claim(a, b, exclusive=True, phase="implementation")
        data = report(self.config, self.ledger, date(2026, 1, 4))
        self.assertEqual(data["project"]["alert"], "high-usage")
        self.assertEqual(data["project"]["remaining"], "70")
        self.assertEqual(data["phases"]["implementation"]["deviation"], "425")

    def test_empty_history_and_projection(self):
        data = report(self.config, self.ledger, date(2026, 1, 4))
        self.assertIsNone(data["projection"]["cycle_usage"])
        self.assertIsNone(data["account"]["latest_balance"])
        self.snap("1800", 2)
        self.snap("1700", 4)
        data = report(self.config, self.ledger, date(2026, 1, 5))
        self.assertEqual(data["projection"]["kind"], "estimate")
        self.assertGreater(Decimal(data["projection"]["cycle_usage"]), 100)

    def test_historical_date_does_not_include_future_records(self):
        self.snap("1800", 2)
        self.snap("1700", 5)
        data = report(self.config, self.ledger, date(2026, 1, 3))
        self.assertEqual(data["account"]["latest_balance"], "1800")
        self.assertEqual(data["account"]["observed_interval_usage"], "0")

    def test_estimate_has_low_confidence_without_history(self):
        data = estimate(self.config, self.ledger, task_type="feature", complexity="medium")
        self.assertEqual(data["confidence"], "low")
        self.assertEqual(data["kind"], "estimate")
        self.assertEqual(data["sample_count"], 0)

    def test_estimates_learn_only_from_comparable_verified_claims(self):
        self.config.data["tasks"] = {
            "sample": {
                "budget": "100",
                "phase": "implementation",
                "task_type": "feature",
                "complexity": "medium",
                "size": "medium",
                "strategy": "balanced",
                "testing": "targeted",
            }
        }
        self.config.validate()
        for day in (2, 4, 6):
            a, b = self.snap("1800", day), self.snap("1750", day + 1)
            self.ledger.claim(a, b, exclusive=True, task="sample", verified=True)
        data = estimate(self.config, self.ledger, task_type="feature", complexity="medium")
        self.assertEqual(data["sample_count"], 3)
        self.assertEqual(data["basis"], "comparable-verified-history")
        self.assertEqual(data["expected"], "50")


if __name__ == "__main__":
    unittest.main()
