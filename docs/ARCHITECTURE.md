# Architecture

The runtime is Python 3.11+ with no third-party dependencies or network clients. The portable Agent Skill is an independent instruction package; the optional CLI supplies deterministic bookkeeping. No MCP server is needed for this release.

| Module | Responsibility |
|---|---|
| `config.py` | Strict schema, exact credit amounts, allocation validation, UTC renewal windows and atomic configuration replacement |
| `ledger.py` | SQLite schema, provenance, canonical UTC timestamps, snapshot transactions and exclusive interval claims |
| `reporting.py` | Cycle filtering, account observations, attributed totals, alerts, deviations and low-confidence projections |
| `estimates.py` | Explicit planning weights and median calibration from comparable verified task intervals |
| `cli.py` | Argument parsing, human/JSON output and actionable error handling |

The source launcher inserts its own `src` directory, so a reviewed checkout works without installation. Standard packaging exposes `starbots-kco`. The source distribution includes the Skill, docs, tests and synthetic demo. The wheel supplies the CLI; import the Skill separately from its GitHub folder.

## Storage contract

The private data directory defaults to `.kiro-credits/`. Configuration is JSON schema version 1. SQLite schema version 1 stores a bound identity (project, balance basis, renewal day), snapshots and claims. Future unknown schema versions are rejected. This release has no destructive history command and no automatic migrations.

Credit inputs use Decimal validation and integer microcredits (1 credit = 1,000,000 units). JSON emits decimal strings. At most six fractional digits are retained; additional precision is rejected, never silently rounded. Estimates round to the nearest microcredit using Python's half-even rule.

Snapshots keep normalized timestamps, balance, project ID, source, source reference, note and optional phase/task/session tags. Claims reference endpoint IDs, preserve context, verification attestation and estimation descriptors, and record creation time. Source labels are user supplied. Neither provenance nor verification is authenticated by this tool.

Writes use SQLite transactions with `BEGIN IMMEDIATE` and overlap validation inside the transaction. Duplicate instants are unique. Backfill revalidates any affected claims before commit. Ordinary reports retain observation/claim separation; a claim does not add another account measurement. Local database foreign keys preserve endpoint references. Configuration edits use temporary-file replacement; configure one writer at a time.

## Attribution and time

Claim endpoints must be chronological, within the same monthly UTC cycle, and include no known balance increases. Intervals may touch but never overlap. Unrelated concurrent use must be excluded by the user's attestation. This cannot be established from account balances alone.

Cycles recur on the configured day, clamped independently for each month. The cycle is `[start 00:00 UTC, next start 00:00 UTC)`. Reports include the chosen date and only measurements in that cycle. A cycle may lack start/end observations, so account totals are explicitly partial. Budget reports use current allocations for historical dates. Separate directories are independent and cannot deduplicate one another.

The estimator treats a verified task interval as one complete comparable observation. It matches type, complexity, repository size, strategy and testing scope. The model strategy is descriptive; no model price table or token conversion exists. Weak or misleading attestations cannot be repaired algorithmically, so every result retains its basis and confidence.

## Extension boundary

The existing modules and JSON reports can support future integrations without a service or daemon. A future adapter must be explicit, opt-in, provenance preserving, and validated against synthetic fixtures. Authorized account access is not permission to collect credentials or session contents. Cross-project aggregation, official export adapters, automatic model changes and MCP remain unimplemented.
