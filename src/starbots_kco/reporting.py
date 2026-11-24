"""Separate account observations, attributed project usage and projections."""

from datetime import datetime, timedelta
from decimal import Decimal

from .config import credits, cycle, display


def budget_status(amount, used, thresholds):
    amount, used = credits(amount), credits(used)
    utilization = Decimal(used) * 100 / amount if amount else None
    level = "unallocated" if amount == 0 and used else "normal"
    if utilization is not None:
        for threshold, label in zip(
            thresholds, ("information", "caution", "high-usage"), strict=False
        ):
            if utilization >= threshold:
                level = label
    return {
        "budget": display(amount),
        "attributed_usage": display(used),
        "remaining": display(amount - used),
        "deviation": display(max(used - amount, 0)),
        "utilization_percent": str(round(utilization, 2)) if utilization is not None else None,
        "alert": level,
    }


def report(config, ledger, as_of):
    data = config.data
    start, end = cycle(as_of, data["renewal_day"])
    cutoff = (as_of + timedelta(days=1)).isoformat()
    snapshots = [
        s for s in ledger.snapshots() if start.isoformat() <= s["at"] < min(end.isoformat(), cutoff)
    ]
    claims = [
        c
        for c in ledger.claims()
        if start.isoformat() <= c["start_at"] and c["end_at"] < min(end.isoformat(), cutoff)
    ]
    usage = 0
    seconds = 0
    warnings = [
        "Advisory only; this tool cannot enforce Kiro billing limits.",
        "Account differences can include activity outside this project.",
    ]
    adjusted = False
    for a, b in zip(snapshots, snapshots[1:], strict=False):
        difference = credits(a["balance"]) - credits(b["balance"])
        if difference < 0:
            adjusted = True
            warnings.append(
                "A balance increase was excluded; account usage is a partial observation."
            )
        else:
            usage += difference
            seconds += (
                datetime.fromisoformat(b["at"]) - datetime.fromisoformat(a["at"])
            ).total_seconds()
    attributed = sum(credits(c["usage"]) for c in claims)
    project = budget_status(
        display(credits(data["project_budget"]) - credits(data["reserve"])),
        display(attributed),
        data["thresholds"],
    )
    project.update({"allocated": data["project_budget"], "reserve": data["reserve"]})
    phases = {
        name: budget_status(
            amount,
            display(sum(credits(c["usage"]) for c in claims if c["phase"] == name)),
            data["thresholds"],
        )
        for name, amount in data["phases"].items()
    }
    tasks = {
        name: budget_status(
            t["budget"],
            display(sum(credits(c["usage"]) for c in claims if c["task"] == name)),
            data["thresholds"],
        )
        for name, t in data["tasks"].items()
    }
    sessions = {
        name: budget_status(
            s["budget"],
            display(sum(credits(c["usage"]) for c in claims if c["session"] == name)),
            data["thresholds"],
        )
        for name, s in data["sessions"].items()
    }
    projected = None
    if seconds >= 86400 and not adjusted:
        projected = display(
            round(Decimal(usage) * Decimal((end - start).days * 86400) / Decimal(str(seconds)))
        )
    if snapshots and datetime.fromisoformat(snapshots[-1]["at"]).date() < as_of:
        warnings.append(
            "Latest balance predates the report date; record a fresh snapshot before planning."
        )
    if not snapshots:
        warnings.append("No snapshots in this cycle; usage is unknown, not proven zero.")
    if project["alert"] != "normal":
        warnings.append(
            "Project budget threshold reached; narrow scope and diagnose retries before continuing."
        )
    return {
        "schema_version": 1,
        "project_id": data["project"],
        "as_of": as_of.isoformat(),
        "cycle": {"start": start.isoformat(), "end_exclusive": end.isoformat(), "timezone": "UTC"},
        "account": {
            "monthly_allowance": data["monthly_allowance"],
            "balance_basis": data["balance_basis"],
            "observed_interval_usage": display(usage),
            "measurement_count": len(snapshots),
            "latest_balance": snapshots[-1]["balance"] if snapshots else None,
            "latest_at": snapshots[-1]["at"] if snapshots else None,
            "sources": sorted({s["source"] for s in snapshots}),
            "coverage": "partial-between-snapshots" if snapshots else "unknown",
            "adjustments_excluded": adjusted,
        },
        "project": project,
        "phases": phases,
        "tasks": tasks,
        "sessions": sessions,
        "claims": claims,
        "projection": {
            "kind": "estimate",
            "cycle_usage": projected,
            "confidence": "low",
            "method": "observed account interval rate extended over the UTC cycle; requires >=24h and no balance increase",
        },
        "warnings": list(dict.fromkeys(warnings)),
        "budget_basis": "current configuration; historical budget versions are not stored",
    }
