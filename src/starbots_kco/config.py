"""Validated configuration and exact credit arithmetic."""

import calendar
import json
import os
import re
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCALE = 1_000_000
PHASES = {"discovery": 10, "planning": 15, "implementation": 45, "testing": 20, "review": 10}
DESCRIPTORS = {
    "task_type": ("feature", "bugfix", "refactor", "docs"),
    "complexity": ("small", "medium", "large"),
    "size": ("small", "medium", "large"),
    "strategy": ("economy", "balanced", "thorough"),
    "testing": ("targeted", "full"),
}


class CreditError(ValueError):
    """An actionable input or local data error."""


def credits(value):
    if isinstance(value, bool):
        raise CreditError("Credits must be a finite non-negative number with at most 6 decimals.")
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > 1_000_000_000:
            raise CreditError("Credits must be between 0 and 1,000,000,000.")
        if not number:
            return 0
        _, coefficient, exponent = number.as_tuple()
        digits = list(coefficient)
        while digits and digits[-1] == 0:
            digits.pop()
            exponent += 1
        if exponent < -6:
            raise CreditError("Credits support at most 6 decimal places.")
        exact = 0
        for digit in digits:
            exact = exact * 10 + digit
        return exact * 10 ** (exponent + 6)
    except (InvalidOperation, TypeError) as exc:
        raise CreditError("Invalid credit amount.") from exc


def display(value):
    return format(Decimal(value) / SCALE, ".6f").rstrip("0").rstrip(".") if value else "0"


def cycle(day, renewal_day):
    if (
        isinstance(renewal_day, bool)
        or not isinstance(renewal_day, int)
        or not 1 <= renewal_day <= 31
    ):
        raise CreditError("Renewal day must be an integer from 1 to 31.")

    def boundary(year, month):
        return date(year, month, min(renewal_day, calendar.monthrange(year, month)[1]))

    start = boundary(day.year, day.month)
    if day < start:
        year, month = (day.year - 1, 12) if day.month == 1 else (day.year, day.month - 1)
        start = boundary(year, month)
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return start, boundary(year, month)


def identifier(value, label="Identifier"):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value):
        raise CreditError(
            f"{label} must use 1-64 lowercase letters, digits, underscores or hyphens."
        )
    return value


class Config:
    def __init__(self, data):
        self.data = data
        self.validate()

    @classmethod
    def create(cls, project, monthly, budget, reserve, renewal_day):
        available = credits(budget) - credits(reserve)
        if available < 0:
            raise CreditError("Reserve cannot exceed the project budget.")
        phases = {}
        remaining = available
        for name, percent in PHASES.items():
            amount = available * percent // 100 if name != "review" else remaining
            phases[name] = display(amount)
            remaining -= amount
        return cls(
            {
                "schema_version": 1,
                "project": project,
                "monthly_allowance": str(monthly),
                "project_budget": str(budget),
                "reserve": str(reserve),
                "renewal_day": renewal_day,
                "balance_basis": "monthly-remaining",
                "thresholds": [50, 75, 90],
                "phases": phases,
                "tasks": {},
                "sessions": {},
            }
        )

    def validate(self):
        data = self.data
        expected = {
            "schema_version",
            "project",
            "monthly_allowance",
            "project_budget",
            "reserve",
            "renewal_day",
            "balance_basis",
            "thresholds",
            "phases",
            "tasks",
            "sessions",
        }
        if (
            not isinstance(data, dict)
            or set(data) != expected
            or type(data["schema_version"]) is not int
            or data["schema_version"] != 1
        ):
            raise CreditError(
                "Invalid configuration fields or unsupported schema_version; expected 1."
            )
        identifier(data["project"], "Project")
        identifier(data["balance_basis"], "Balance basis")
        cycle(date.today(), data["renewal_day"])
        monthly, budget, reserve = (
            credits(data[k]) for k in ("monthly_allowance", "project_budget", "reserve")
        )
        if monthly <= 0 or budget <= 0 or budget > monthly or reserve > budget:
            raise CreditError(
                "Require 0 < project budget <= monthly allowance and reserve <= budget."
            )
        thresholds = data["thresholds"]
        if (
            not isinstance(thresholds, list)
            or len(thresholds) != 3
            or any(type(v) is not int or not 0 < v <= 100 for v in thresholds)
            or thresholds != sorted(set(thresholds))
        ):
            raise CreditError(
                "Thresholds must be three strictly increasing integer percentages in 1..100."
            )
        for group in ("phases", "tasks", "sessions"):
            if not isinstance(data[group], dict):
                raise CreditError(f"{group} must be an object.")
            for name in data[group]:
                identifier(name)
        if (
            not data["phases"]
            or sum(credits(v) for v in data["phases"].values()) > budget - reserve
        ):
            raise CreditError("Phase allocations must fit the project budget after its reserve.")
        for task in data["tasks"].values():
            if not isinstance(task, dict) or set(task) != {"budget", "phase", *DESCRIPTORS}:
                raise CreditError("Each task needs budget, phase and all estimation descriptors.")
            if not isinstance(task["phase"], str) or task["phase"] not in data["phases"]:
                raise CreditError("Task phase does not exist.")
            credits(task["budget"])
            for key, options in DESCRIPTORS.items():
                if task[key] not in options:
                    raise CreditError(f"Invalid task {key}; choose {', '.join(options)}.")
        for phase, amount in data["phases"].items():
            if sum(
                credits(t["budget"]) for t in data["tasks"].values() if t["phase"] == phase
            ) > credits(amount):
                raise CreditError(f"Task budgets exceed phase {phase}.")
        for session in data["sessions"].values():
            if (
                not isinstance(session, dict)
                or set(session) != {"budget", "task"}
                or not isinstance(session["task"], str)
                or session["task"] not in data["tasks"]
            ):
                raise CreditError("Each session needs a budget and an existing task.")
            credits(session["budget"])
        for name, task in data["tasks"].items():
            if sum(
                credits(s["budget"]) for s in data["sessions"].values() if s["task"] == name
            ) > credits(task["budget"]):
                raise CreditError(f"Session budgets exceed task {name}.")


def load_config(path):
    try:
        return Config(json.loads(Path(path).read_text(encoding="utf-8"), parse_float=str))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CreditError(
            "Cannot read configuration. Run init first, or restore a valid private backup."
        ) from exc


def save_config(path, config, *, create=False):
    config.validate()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config.data, indent=2) + "\n"
    if create:
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(text)
        except FileExistsError as exc:
            raise CreditError(
                "Configuration already exists; use budget to adjust allocations."
            ) from exc
        return
    fd, temporary = tempfile.mkstemp(prefix="config-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
