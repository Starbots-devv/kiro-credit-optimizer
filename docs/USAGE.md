# Usage

Run `python kco.py` from the source checkout or replace it with your installed `starbots-kco` executable. Python must be 3.11+. Use `py -3` on Windows or `python3` on macOS/Linux where needed. Each command supports `--help` and `--json`.

## Private workspace

The default data location is `.kiro-credits/` in the current working directory. This repository ignores it. **Other repositories must add their own ignore rule** before collecting real data. You may select an explicit directory with `--data-dir` before the command. Use an absolute path when moving between workspaces.

```bash
python kco.py init --project example-app --monthly 2000 --budget 1000 --reserve 100 --renewal-day 1
python kco.py config --json
python kco.py doctor
```

The 2,000-credit monthly allowance is a configurable example, not a subscription lookup. `init` refuses to replace existing configuration. Amounts must be finite, non-negative, at most 1,000,000,000 credits and have at most six decimal places. Identifiers use lowercase letters, digits, `_` and `-` (1–64 characters).

## Allocate budgets

The project budget cannot exceed the reference monthly allowance. Reserve is kept outside the spendable amount. Initial phases receive 10/15/45/20/10 percent of spendable credits for discovery/planning/implementation/testing/review. For the example above, those amounts are 90/135/405/180/90.

```bash
python kco.py budget --monthly 2500 --project-budget 1200 --reserve 120
python kco.py budget --thresholds 50,75,90
python kco.py budget --phase testing --amount 200
python kco.py budget --task auth-fix --phase implementation --amount 100 --task-type bugfix --complexity small --size medium --strategy balanced --testing targeted
python kco.py budget --session first-pass --task auth-fix --amount 50
```

Changing the project budget or reserve **rebuilds phase allocations using default percentages**. Existing task/session allocations are retained and must still fit; otherwise the entire update fails. A phase change adjusts only that phase; unallocated funds are permitted. Tasks must fit their parent phase; sessions must fit their parent task. Use one configuration writer at a time.

Thresholds are three strictly increasing integer percentages. They produce `information`, `caution` and `high-usage` statuses. Usage against a zero allocation is `unallocated`. The CLI never pauses Kiro or enforces payment limits.

## Record balances

Record a fresh balance from an authorized source, such as Kiro's `/usage` display. Use actual amounts only in your private ledger. These examples are synthetic:

```bash
python kco.py snapshot --balance 1800 --at 2026-01-02T12:00:00Z --reference "Synthetic official-balance fixture"
python kco.py snapshot --balance 1760 --at 2026-01-03T12:00:00Z --source manual-official --reference "Synthetic official-balance fixture" --session first-pass
```

Without `--at`, the timestamp is the current UTC instant. Explicit timestamps require an ISO 8601 timezone, including `Z` or an offset such as `-06:00`; naive timestamps and invalid dates fail. Equivalent instants are duplicate records even with different offsets. Backdated records are allowed if they do not invalidate an existing claim. Context labels must refer to configured phases/tasks/sessions.

| Source value | What you are asserting |
|---|---|
| `manual-official` | You transcribed an official account balance |
| `official-report` | An authorized official report supplied the balance |
| `authorized-local` | A reviewed local tool supplied an actual credit balance |

All three are manually supplied labels. No label authenticates or fetches data. Include a short non-sensitive `--reference`; optional `--note` text stays private. Do not enter an estimate as a balance. Third-party token totals, cumulative credit totals and dollar estimates are not remaining balances.

Use the same credit pool throughout a ledger. The default `--balance-basis monthly-remaining` describes the chosen pool. If you use a different official pool, set a meaningful basis on `init` and keep it consistent. Add-ons, corrections or pool changes can make subtraction invalid. An increase is excluded from account difference totals and blocks claims across the increase. Consumption during an adjustment gap remains unknown, even if balances appear to decrease overall.

## Attribute an interval

Snapshot tags do not attribute consumption. The report initially shows account observations with zero attributed project usage. Only use a claim when you can attest that no other account activity occurred over the **entire** interval:

```bash
python kco.py claim 1 2 --session first-pass --exclusive-account
```

Use the snapshot IDs returned by your ledger. Phase and task are inferred from the session's allocation. Claims use half-open intervals `[start, end)`; adjacent claims can share endpoints. Duplicate/overlapping claims, reversed endpoints, missing records, balance increases and renewal crossings fail without writing partial data.

`--verified` additionally attests that the interval represents a **complete task** and all necessary checks passed. A verified task with configured descriptors can inform future estimates. Do not mark partial session work verified. The tool records your attestation; it does not run the project's tests or independently verify exclusivity. Separate ledgers cannot detect each other's overlaps.

## Reports and renewal

```bash
python kco.py status
python kco.py report --as-of 2026-01-04 --json
```

Reports use the configured monthly renewal day at **00:00 UTC**, clamping days 29–31 to the last day of short months. This is a local planning convention, not a claim about your actual billing timezone. A renewal day or pool change needs a **new data directory** because the ledger binds those identity fields. The historical ledger remains intact.

`--as-of` includes that entire UTC date and excludes later measurements. Reports show current configuration budgets even for historical cycles; budget versions are not archived. No snapshots means unknown usage, not evidence of no consumption. Account observed totals cover only differences between snapshots inside the selected cycle; they do not include missing boundaries. A latest balance is an observation at its recorded time, not a live query.

Project totals add claims once; phase, task and session values are breakdowns of the same claims and must not be added to project totals. Unassigned project claims can make phase totals smaller than the project total. Remaining budget can be negative; deviation is the positive amount above allocation.

A cycle projection extends the account observation rate across the entire renewal cycle, requiring at least 24 hours between comparable observations and no recorded increase. It is always a low-confidence estimate. Sparse history, adjustments and changing workloads make it unsuitable as a billing forecast.

## Estimate a task

```bash
python kco.py estimate --task-type feature --complexity medium --size large --strategy balanced --testing full --phases 3 --retries 1 --uncertainty 0.30 --json
```

The heuristic base is feature 20, bugfix 15, refactor 25 or docs 5 credits. Complexity weights are 0.5/1/2; repository size 0.8/1/1.5; strategy 0.8/1/1.4; full testing 1.4. These are **uncalibrated planning weights**, not Kiro prices, token conversions or measured consumption. Defaults: feature, medium complexity/size, balanced strategy, targeted testing, one phase, zero expected retries, 25% uncertainty.

With at least three verified claims matching all five descriptors, the median complete-task usage replaces the heuristic base. Confidence remains low until five samples, then moderate. Claims retain their original descriptors when budgets change. Add 15% per extra phase (1–5 total) and 20% per expected retry (0–5). The range is expected usage ± the configured uncertainty (0–1); it is not a statistically calibrated confidence interval. More history does not guarantee accuracy.

## Export, backup and recovery

```bash
python kco.py export --json > .kiro-credits/usage-export.json
```

The export includes all snapshots and claims, configuration, identifiers, timestamps, provenance, references and notes. Review it before sharing. **No import/restore adapter is implemented** in v0.1. To back up the operational ledger, stop all commands and copy the entire private data directory to private storage. Restore that directory while no commands are running. Do not replace just one file from an incompatible backup.

`doctor` checks SQLite integrity and compatible configuration. Errors exit with status 2 and preserve existing history. Never delete a corrupt database just to make a check pass; retain the files and recover a private backup. Successful commands exit 0. With `--json`, handled runtime errors are JSON on stderr; argument parser errors use argparse's standard usage text.

See [data handling](DATA_HANDLING.md) and [architecture](ARCHITECTURE.md).
