import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kco synthetic ü ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, *args, ok=True):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "kco.py"),
                "--data-dir",
                str(self.root / "private data"),
                *args,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        self.assertEqual(result.returncode, 0 if ok else 2, result.stdout + result.stderr)
        if ok:
            return json.loads(result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def init(self):
        return self.run_cli(
            "init",
            "--project",
            "synthetic",
            "--monthly",
            "2000",
            "--budget",
            "1000",
            "--reserve",
            "100",
            "--json",
        )

    def snapshot(self, amount, day):
        return self.run_cli(
            "snapshot",
            "--balance",
            amount,
            "--at",
            f"2026-01-{day:02d}T12:00:00Z",
            "--reference",
            "synthetic fixture",
            "--json",
        )["snapshot_id"]

    def test_complete_workflow(self):
        self.init()
        a, b = self.snapshot("1800", 2), self.snapshot("1700", 3)
        self.run_cli(
            "claim", str(a), str(b), "--phase", "implementation", "--exclusive-account", "--json"
        )
        data = self.run_cli("report", "--as-of", "2026-01-04", "--json")
        self.assertEqual(data["project"]["attributed_usage"], "100")
        self.assertEqual(data["phases"]["implementation"]["remaining"], "305")
        export = self.run_cli("export", "--json")
        self.assertEqual(len(export["snapshots"]), 2)
        self.assertEqual(export["snapshots"][0]["source"], "manual-official")
        self.assertTrue(self.run_cli("doctor", "--json")["integrity_ok"])

    def test_task_and_session_budgets(self):
        self.init()
        self.run_cli(
            "budget",
            "--task",
            "small-fix",
            "--phase",
            "implementation",
            "--amount",
            "100",
            "--task-type",
            "bugfix",
            "--json",
        )
        self.run_cli(
            "budget", "--session", "first-pass", "--task", "small-fix", "--amount", "50", "--json"
        )
        a, b = self.snapshot("1800", 2), self.snapshot("1760", 3)
        self.run_cli(
            "claim", str(a), str(b), "--session", "first-pass", "--exclusive-account", "--json"
        )
        report = self.run_cli("status", "--as-of", "2026-01-04", "--json")
        self.assertEqual(report["tasks"]["small-fix"]["remaining"], "60")
        self.assertEqual(report["sessions"]["first-pass"]["alert"], "caution")

    def test_duplicate_init_preserves_existing_config(self):
        self.init()
        config = self.root / "private data" / "config.json"
        before = config.read_bytes()
        self.run_cli("init", "--project", "other", "--json", ok=False)
        self.assertEqual(before, config.read_bytes())

    def test_invalid_budget_does_not_write(self):
        self.init()
        before = self.run_cli("config", "--json")
        self.run_cli("budget", "--reserve", "1001", "--json", ok=False)
        self.assertEqual(before, self.run_cli("config", "--json"))

    def test_missing_config_and_bad_date_fail_cleanly(self):
        self.run_cli("report", "--json", ok=False)
        self.init()
        self.run_cli("report", "--as-of", "invalid", "--json", ok=False)
        self.run_cli("snapshot", "--balance", "NaN", "--reference", "synthetic", ok=False)

    def test_corrupt_database_preserved(self):
        self.init()
        db = self.root / "private data" / "usage.sqlite3"
        db.write_bytes(b"synthetic corrupted database")
        self.run_cli("doctor", "--json", ok=False)
        self.assertEqual(db.read_bytes(), b"synthetic corrupted database")

    def test_missing_database_is_not_recreated(self):
        self.init()
        self.snapshot("1800", 2)
        db = self.root / "private data" / "usage.sqlite3"
        db.unlink()
        self.run_cli("doctor", "--json", ok=False)
        self.assertFalse(db.exists())

    def test_empty_database_is_not_reinitialized(self):
        self.init()
        db = self.root / "private data" / "usage.sqlite3"
        db.write_bytes(b"")
        self.run_cli("report", "--json", ok=False)
        self.assertEqual(db.read_bytes(), b"")

    def test_oversized_snapshot_ids_fail_cleanly(self):
        self.init()
        self.run_cli("claim", "9223372036854775808", "2", "--exclusive-account", "--json", ok=False)

    def test_estimate_and_config(self):
        self.init()
        value = self.run_cli("estimate", "--task-type", "bugfix", "--complexity", "small", "--json")
        self.assertEqual(value["kind"], "estimate")
        self.assertEqual(value["confidence"], "low")
        self.assertEqual(self.run_cli("config", "--json")["project"], "synthetic")

    def test_ordinary_commands_do_not_access_network(self):
        guard = self.root / "sitecustomize.py"
        guard.write_text(
            "import socket\ndef blocked(*args, **kwargs):\n    raise RuntimeError('Network forbidden in offline test')\nsocket.socket = blocked\nsocket.create_connection = blocked\n",
            encoding="utf-8",
        )
        original = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(self.root)
        try:
            self.init()
            self.snapshot("1800", 2)
            self.run_cli("report", "--json")
            self.run_cli("estimate", "--json")
            self.run_cli("doctor", "--json")
        finally:
            if original is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = original


if __name__ == "__main__":
    unittest.main()
