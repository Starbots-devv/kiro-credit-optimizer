"""Reproducible synthetic workflow; never reads a real Kiro account."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="starbots-synthetic-") as directory:
        base = [sys.executable, str(ROOT / "kco.py"), "--data-dir", directory]

        def run(*args):
            process = subprocess.run(
                [*base, *args, "--json"], capture_output=True, text=True, check=True, timeout=30
            )
            return json.loads(process.stdout)

        run(
            "init",
            "--project",
            "example-app",
            "--monthly",
            "2000",
            "--budget",
            "1000",
            "--reserve",
            "100",
        )
        a = run(
            "snapshot",
            "--balance",
            "1800",
            "--at",
            "2026-01-02T12:00:00Z",
            "--reference",
            "Synthetic starting balance",
        )
        b = run(
            "snapshot",
            "--balance",
            "1700",
            "--at",
            "2026-01-03T12:00:00Z",
            "--reference",
            "Synthetic ending balance",
        )
        before = run("report", "--as-of", "2026-01-04")
        if before["project"]["attributed_usage"] != "0":
            raise RuntimeError("Account differences must remain unattributed by default.")
        run(
            "claim",
            str(a["snapshot_id"]),
            str(b["snapshot_id"]),
            "--phase",
            "implementation",
            "--exclusive-account",
        )
        result = run("report", "--as-of", "2026-01-04")
        if (
            result["account"]["observed_interval_usage"],
            result["project"]["attributed_usage"],
            result["project"]["remaining"],
        ) != ("100", "100", "800"):
            raise RuntimeError("Synthetic budget calculation failed.")
        if not run("doctor")["integrity_ok"]:
            raise RuntimeError("Synthetic ledger integrity failed.")
        print("Synthetic demo | example-app | January 2026")
        print("Account observed interval usage: 100 credits")
        print("Project attributed usage:        100 credits")
        print("Spendable project remainder:     800 credits")
        print("Separate project reserve:        100 credits")
        print("Temporary data removed on exit. No real account accessed.")


if __name__ == "__main__":
    main()
