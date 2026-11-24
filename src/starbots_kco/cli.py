"""Small offline CLI for budgets and explicit usage accounting."""

import argparse
import json
import sqlite3
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from . import __version__
from .config import DESCRIPTORS, Config, CreditError, identifier, load_config, save_config
from .estimates import estimate
from .ledger import SOURCES, Ledger
from .reporting import report


def parser():
    root = argparse.ArgumentParser(
        description="Starbots Kiro Credit Optimizer: local, advisory budgets."
    )
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument(
        "--data-dir",
        type=Path,
        default=Path(".kiro-credits"),
        help="Private workspace directory; put before the command.",
    )
    commands = root.add_subparsers(dest="command", required=True)

    def command(name, description):
        sub = commands.add_parser(name, help=description, description=description)
        sub.add_argument(
            "--json",
            action="store_true",
            help="Emit machine-readable JSON; credit values are decimal strings.",
        )
        return sub

    def descriptors(sub, default=None):
        for key, values in DESCRIPTORS.items():
            sub.add_argument("--" + key.replace("_", "-"), choices=values, default=default)

    def context(sub):
        sub.add_argument("--phase")
        sub.add_argument("--task")
        sub.add_argument("--session")

    init = command("init", "Create validated private configuration and an empty ledger.")
    init.add_argument("--project", required=True)
    init.add_argument(
        "--monthly", default="2000", help="Configurable reference allowance, not a pricing lookup."
    )
    init.add_argument("--budget", default="1000")
    init.add_argument("--reserve", default="100")
    init.add_argument(
        "--renewal-day", type=int, default=1, help="UTC day 1..31, clamped to month end."
    )
    init.add_argument(
        "--balance-basis",
        default="monthly-remaining",
        help="One consistent credit pool for the entire ledger.",
    )

    budget = command("budget", "Adjust project, phase, task or session allocations.")
    budget.add_argument("--monthly")
    budget.add_argument("--project-budget")
    budget.add_argument("--reserve")
    budget.add_argument("--thresholds", help="Three percentages, for example 50,75,90.")
    context(budget)
    budget.add_argument("--amount")
    descriptors(budget)

    snap = command(
        "snapshot", "Record a balance; this never attributes account usage to a project."
    )
    snap.add_argument("--balance", required=True)
    snap.add_argument(
        "--at", default=None, help="ISO 8601 timestamp with timezone; default now in UTC."
    )
    snap.add_argument("--source", choices=SOURCES, default="manual-official")
    snap.add_argument("--reference", required=True, help="Short non-sensitive source description.")
    snap.add_argument("--note", default="")
    context(snap)

    claim = command("claim", "Attribute an exclusive account interval to this project.")
    claim.add_argument("start", type=int)
    claim.add_argument("end", type=int)
    claim.add_argument(
        "--exclusive-account",
        action="store_true",
        help="Attest no concurrent or unrelated account consumption.",
    )
    claim.add_argument(
        "--verified",
        action="store_true",
        help="Attest this interval covers a complete task and necessary checks passed; eligible for estimation history.",
    )
    context(claim)

    for name in ("status", "report"):
        sub = command(name, "Show cycle observations, allocated budgets and advisory alerts.")
        sub.add_argument("--as-of", help="UTC report date YYYY-MM-DD; default today.")
    est = command(
        "estimate", "Estimate a task using explicit heuristics or comparable verified history."
    )
    descriptors(est)
    est.add_argument("--phases", type=int, default=1)
    est.add_argument("--retries", type=int, default=0)
    est.add_argument("--uncertainty", default="0.25")
    command("config", "Inspect validated private configuration.")
    command("doctor", "Check runtime, configuration and SQLite integrity without contacting Kiro.")
    command(
        "export",
        "Write private configuration, snapshots and claims to stdout; review before sharing.",
    )
    return root


def update_budget(args, config):
    data = json.loads(json.dumps(config.data))
    for arg, field in (
        ("monthly", "monthly_allowance"),
        ("project_budget", "project_budget"),
        ("reserve", "reserve"),
    ):
        if getattr(args, arg) is not None:
            data[field] = getattr(args, arg)
    if args.project_budget is not None or args.reserve is not None:
        data["phases"] = Config.create(
            data["project"],
            data["monthly_allowance"],
            data["project_budget"],
            data["reserve"],
            data["renewal_day"],
        ).data["phases"]
    if args.thresholds is not None:
        try:
            data["thresholds"] = [int(v) for v in args.thresholds.split(",")]
        except ValueError as exc:
            raise CreditError("Thresholds must be comma-separated integers.") from exc
    if args.amount is not None:
        if args.session:
            identifier(args.session, "Session")
            if not args.task or args.phase:
                raise CreditError("A session allocation needs --task and no --phase.")
            data["sessions"][args.session] = {"budget": args.amount, "task": args.task}
        elif args.task:
            identifier(args.task, "Task")
            existing = data["tasks"].get(args.task, {})
            phase = args.phase or existing.get("phase")
            values = {
                k: getattr(args, k)
                or existing.get(k)
                or {
                    "task_type": "feature",
                    "complexity": "medium",
                    "size": "medium",
                    "strategy": "balanced",
                    "testing": "targeted",
                }[k]
                for k in DESCRIPTORS
            }
            data["tasks"][args.task] = {"budget": args.amount, "phase": phase, **values}
        elif args.phase:
            identifier(args.phase, "Phase")
            data["phases"][args.phase] = args.amount
        else:
            raise CreditError("--amount requires --phase, --task or --session.")
    elif (
        args.phase
        or args.task
        or args.session
        or any(getattr(args, k) is not None for k in DESCRIPTORS)
    ):
        raise CreditError("Scope and descriptor changes require --amount.")
    return Config(data)


def render(result):
    if "cycle" in result:
        account, project = result["account"], result["project"]
        print(f"Starbots Kiro Credit Optimizer | {result['project_id']} | {result['as_of']} UTC")
        print(
            f"Cycle: {result['cycle']['start']} to {result['cycle']['end_exclusive']} (end exclusive)"
        )
        print(
            f"Account observed intervals: {account['observed_interval_usage']} credits | coverage: {account['coverage']}"
        )
        print(
            f"Latest recorded balance: {account['latest_balance'] or 'unknown'} | sources: {', '.join(account['sources']) or 'none'}"
        )
        print(
            f"Project attributed: {project['attributed_usage']} / {project['budget']} | remaining: {project['remaining']} | reserve: {project['reserve']} | {project['alert']}"
        )
        for group in ("phases", "tasks", "sessions"):
            for name, value in result[group].items():
                print(
                    f"  {group[:-1]:7} {name:20} {value['attributed_usage']:>10} / {value['budget']:<10} {value['alert']}"
                )
        print(
            f"Estimated cycle account usage: {result['projection']['cycle_usage'] or 'insufficient data'} (low confidence)"
        )
        for warning in result["warnings"]:
            print(f"Notice: {warning}")
    elif result.get("kind") == "estimate":
        print(
            f"Estimated: {result['expected']} credits | range: {result['low']}..{result['high']} | {result['confidence']} confidence"
        )
        print(f"Basis: {result['basis']} | comparable verified samples: {result['sample_count']}")
        for line in result["recommendations"]:
            print(f"- {line}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=True))


def execute(args):
    directory = args.data_dir.expanduser().resolve()
    config_path = directory / "config.json"
    if args.command == "init":
        if (directory / "usage.sqlite3").exists():
            raise CreditError(
                "Ledger already exists; preserve it and restore its matching configuration."
            )
        config = Config.create(
            args.project, args.monthly, args.budget, args.reserve, args.renewal_day
        )
        config.data["balance_basis"] = args.balance_basis
        save_config(config_path, config, create=True)
    else:
        config = load_config(config_path)
    ledger = Ledger(directory / "usage.sqlite3", config, create=args.command == "init")
    try:
        if args.command == "init":
            return {"initialized": True, "project": config.data["project"], "version": __version__}
        if args.command == "config":
            return config.data
        if args.command == "budget":
            updated = update_budget(args, config)
            save_config(config_path, updated)
            return updated.data
        if args.command == "snapshot":
            sid = ledger.snapshot(
                args.balance,
                args.at or datetime.now(UTC).isoformat(),
                args.source,
                args.reference,
                note=args.note,
                phase=args.phase,
                task=args.task,
                session=args.session,
            )
            return {
                "snapshot_id": sid,
                "source": args.source,
                "attribution": "unattributed-account-balance",
            }
        if args.command == "claim":
            cid = ledger.claim(
                args.start,
                args.end,
                exclusive=args.exclusive_account,
                phase=args.phase,
                task=args.task,
                session=args.session,
                verified=args.verified,
            )
            return {"claim_id": cid, "attribution": "user-attested-exclusive-account"}
        if args.command in ("status", "report"):
            try:
                as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(UTC).date()
                if not 2 <= as_of.year <= 9998:
                    raise ValueError("year out of range")
            except ValueError as exc:
                raise CreditError(
                    "Report date must be YYYY-MM-DD with a year in 0002..9998."
                ) from exc
            return report(config, ledger, as_of)
        if args.command == "estimate":
            defaults = {
                "task_type": "feature",
                "complexity": "medium",
                "size": "medium",
                "strategy": "balanced",
                "testing": "targeted",
            }
            return estimate(
                config,
                ledger,
                **{k: getattr(args, k) or v for k, v in defaults.items()},
                phases=args.phases,
                retries=args.retries,
                uncertainty=args.uncertainty,
            )
        if args.command == "doctor":
            integrity = ledger.db.execute("PRAGMA integrity_check").fetchall()
            if len(integrity) != 1 or integrity[0][0] != "ok":
                raise CreditError(
                    "Ledger integrity check failed; preserve files and restore a private backup."
                )
            return {
                "version": __version__,
                "python": sys.version.split()[0],
                "integrity_ok": True,
                "configuration_ok": True,
                "snapshot_count": len(ledger.snapshots()),
                "claim_count": len(ledger.claims()),
                "network_access": False,
                "live_kiro_connection": False,
            }
        if args.command == "export":
            return {
                "schema_version": 1,
                "privacy": "private; review identifiers, references and notes before sharing",
                "config": config.data,
                "snapshots": ledger.snapshots(),
                "claims": ledger.claims(),
            }
        raise CreditError("Unknown command.")
    finally:
        ledger.close()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            render(result)
        return 0
    except (CreditError, OSError, sqlite3.DatabaseError, UnicodeError, TypeError) as exc:
        message = (
            str(exc)
            if isinstance(exc, CreditError)
            else f"Local data error ({type(exc).__name__}); preserve your files, check permissions or restore a private backup."
        )
        print(json.dumps({"error": message}) if args.json else f"Error: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
