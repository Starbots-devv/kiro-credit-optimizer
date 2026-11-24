"""Transactional snapshots and non-overlapping, user-attested attribution."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .config import CreditError, credits, cycle, display

SOURCES = ("manual-official", "official-report", "authorized-local")


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timezone missing")
        return parsed.astimezone(UTC).isoformat(timespec="microseconds")
    except (ValueError, AttributeError, OverflowError) as exc:
        raise CreditError(
            "Timestamp must be ISO 8601 with a timezone, such as 2026-01-02T12:00:00Z."
        ) from exc


class Ledger:
    def __init__(self, path, config, *, create=False):
        self.config = config
        path = Path(path).resolve()
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                path.touch(exist_ok=False)
            except FileExistsError as exc:
                raise CreditError(
                    "Ledger already exists; restore its matching configuration instead of reinitializing."
                ) from exc
        elif not path.is_file() or path.stat().st_size == 0:
            raise CreditError(
                "Ledger is missing or empty; preserve your configuration and restore a private backup."
            )
        self.db = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=10)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA foreign_keys=ON")
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise CreditError(
                    "Unsupported ledger schema; restore a compatible version, never reset history."
                )
            if version == 0:
                if not create:
                    raise CreditError(
                        "Uninitialized or unrecognized ledger; restore a compatible private backup."
                    )
                if self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise CreditError("Unrecognized database; it will not be overwritten.")
                self.db.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE snapshots (
                        id INTEGER PRIMARY KEY, at TEXT NOT NULL UNIQUE,
                        balance INTEGER NOT NULL CHECK(balance >= 0), project TEXT NOT NULL,
                        source TEXT NOT NULL, reference TEXT NOT NULL, note TEXT NOT NULL,
                        phase TEXT, task TEXT, session TEXT
                    );
                    CREATE TABLE claims (
                        id INTEGER PRIMARY KEY, start_id INTEGER NOT NULL REFERENCES snapshots(id),
                        end_id INTEGER NOT NULL REFERENCES snapshots(id), phase TEXT, task TEXT,
                        session TEXT, verified INTEGER NOT NULL, descriptors TEXT NOT NULL,
                        created_at TEXT NOT NULL, UNIQUE(start_id, end_id)
                    );
                    PRAGMA user_version=1;
                    COMMIT;
                """)
            identity = json.dumps(
                {k: config.data[k] for k in ("project", "balance_basis", "renewal_day")},
                sort_keys=True,
            )
            with self.db:
                self.db.execute(
                    "INSERT OR IGNORE INTO metadata VALUES ('identity', ?)", (identity,)
                )
            actual = self.db.execute("SELECT value FROM metadata WHERE key='identity'").fetchone()[
                0
            ]
            if actual != identity:
                raise CreditError(
                    "Project, balance basis or renewal day differs from this ledger; use a new private data directory."
                )
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def _context(self, phase, task, session):
        data = self.config.data
        if session:
            if session not in data["sessions"]:
                raise CreditError("Unknown session; allocate it with budget first.")
            expected_task = data["sessions"][session]["task"]
            if task and task != expected_task:
                raise CreditError("Session does not belong to this task.")
            task = expected_task
        if task:
            if task not in data["tasks"]:
                raise CreditError("Unknown task; allocate it with budget first.")
            expected_phase = data["tasks"][task]["phase"]
            if phase and phase != expected_phase:
                raise CreditError("Task does not belong to this phase.")
            phase = expected_phase
        if phase and phase not in data["phases"]:
            raise CreditError("Unknown phase.")
        return phase, task, session

    def snapshot(
        self, balance, at, source, reference, *, note="", phase=None, task=None, session=None
    ):
        amount, at = credits(balance), timestamp(at)
        if source not in SOURCES:
            raise CreditError(f"Source must be one of {', '.join(SOURCES)}.")
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 300:
            raise CreditError("Provide a non-sensitive source reference of 1-300 characters.")
        if not isinstance(note, str) or len(note) > 1000:
            raise CreditError("Notes must be text of at most 1000 characters.")
        phase, task, session = self._context(phase, task, session)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            cursor = self.db.execute(
                "INSERT INTO snapshots(at,balance,project,source,reference,note,phase,task,session) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    at,
                    amount,
                    self.config.data["project"],
                    source,
                    reference.strip(),
                    note,
                    phase,
                    task,
                    session,
                ),
            )
            for claim in self.claims():
                if claim["start_at"] < at < claim["end_at"]:
                    self._validate_interval(claim["start_id"], claim["end_id"])
            self.db.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            self.db.rollback()
            raise CreditError(
                "A snapshot already exists at that timestamp; use a distinct measurement."
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def snapshots(self):
        return [
            dict(row, balance=display(row["balance"]))
            for row in self.db.execute("SELECT * FROM snapshots ORDER BY at")
        ]

    def _validate_interval(self, start_id, end_id):
        if any(
            type(value) is not int or not 1 <= value <= 9223372036854775807
            for value in (start_id, end_id)
        ):
            raise CreditError("Snapshot IDs must be positive 64-bit integers.")
        a = self.db.execute("SELECT * FROM snapshots WHERE id=?", (start_id,)).fetchone()
        b = self.db.execute("SELECT * FROM snapshots WHERE id=?", (end_id,)).fetchone()
        if a is None or b is None or a["at"] >= b["at"]:
            raise CreditError("Choose existing start/end snapshots in chronological order.")
        start_day, end_day = (datetime.fromisoformat(row["at"]).date() for row in (a, b))
        if cycle(start_day, self.config.data["renewal_day"]) != cycle(
            end_day, self.config.data["renewal_day"]
        ):
            raise CreditError("An interval cannot cross a renewal boundary.")
        rows = self.db.execute(
            "SELECT balance FROM snapshots WHERE at>=? AND at<=? ORDER BY at", (a["at"], b["at"])
        ).fetchall()
        if any(right[0] > left[0] for left, right in zip(rows, rows[1:], strict=False)):
            raise CreditError(
                "Balance increased within the interval; split around the adjustment and record new baselines."
            )
        return a, b

    def claim(
        self,
        start_id,
        end_id,
        *,
        exclusive=False,
        phase=None,
        task=None,
        session=None,
        verified=False,
    ):
        if not exclusive:
            raise CreditError(
                "Attribution requires --exclusive-account: confirm no other account activity occurred."
            )
        phase, task, session = self._context(phase, task, session)
        descriptors = {
            k: v
            for k, v in self.config.data["tasks"].get(task, {}).items()
            if k not in ("budget", "phase")
        }
        try:
            self.db.execute("BEGIN IMMEDIATE")
            a, b = self._validate_interval(start_id, end_id)
            if self.db.execute(
                "SELECT c.id FROM claims c JOIN snapshots a ON c.start_id=a.id JOIN snapshots b ON c.end_id=b.id WHERE a.at<? AND b.at>?",
                (b["at"], a["at"]),
            ).fetchone():
                raise CreditError("This claim duplicates or overlaps an existing claim.")
            cursor = self.db.execute(
                "INSERT INTO claims(start_id,end_id,phase,task,session,verified,descriptors,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    start_id,
                    end_id,
                    phase,
                    task,
                    session,
                    int(verified),
                    json.dumps(descriptors, sort_keys=True),
                    timestamp(datetime.now(UTC).isoformat()),
                ),
            )
            self.db.commit()
            return cursor.lastrowid
        except Exception:
            self.db.rollback()
            raise

    def claims(self):
        result = []
        for row in self.db.execute(
            "SELECT c.*, a.at AS start_at, b.at AS end_at, a.balance-b.balance AS usage, a.source AS start_source, b.source AS end_source, a.reference AS start_reference, b.reference AS end_reference FROM claims c JOIN snapshots a ON c.start_id=a.id JOIN snapshots b ON c.end_id=b.id ORDER BY a.at"
        ):
            item = dict(row)
            item["usage"] = display(item["usage"])
            item["descriptors"] = json.loads(item["descriptors"])
            item["verified"] = bool(item["verified"])
            item["attribution"] = "user-attested-exclusive-account"
            result.append(item)
        return result
