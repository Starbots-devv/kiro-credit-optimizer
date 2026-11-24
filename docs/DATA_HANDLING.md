# Data handling and privacy

The CLI has no network client, telemetry, daemon, API keys or authentication integration. It does not read Kiro credentials, prompt/response logs, session databases or repository contents. Its inputs are balances and context deliberately provided by the operator.

## Stored data

By default, `.kiro-credits/config.json` contains the project identifier, budgets, balance basis, renewal day, thresholds and task/session descriptors. `.kiro-credits/usage.sqlite3` contains snapshot timestamps, balances, project/context labels, source labels, references, notes and interval claims. Journals may briefly accompany database transactions. No account identifier is required.

Treat every file in that directory as private. Local storage inherits the selected directory's operating-system permissions; it is **not encrypted** and this tool does not promise isolation from other users on the machine. Choose a directory protected by your OS account, especially on shared systems. Do not place real data in shared/synced folders unintentionally. Avoid secrets in names, references or notes.

The repository ignores its default data directory, databases, logs, environment secrets, keys and local environments. When using the CLI from another repository, add equivalent ignore rules there. Custom directories and redirected exports require your own protection. Never post real exports, balances, account identifiers, client names or session histories in public issues.

## Integrity and deletion

Snapshot/claim writes are transactional and conflicting records fail. Config replacement is atomic; use one budget/configuration writer at a time. `doctor` checks SQLite integrity, but cannot verify the truth of a manually entered balance, source label, exclusive-use attestation or successful test claim.

For backups, close commands and copy the entire private data directory to protected storage. Preserve corrupt files before attempting recovery. No import adapter or destructive repair/reset command is provided. Unknown schema versions fail rather than resetting history.

To remove your data, close all commands, confirm the exact private directory you selected, and delete that directory using your file manager. This removes configuration and all local history for that ledger. Delete any separate exports and backups you no longer want. File deletion is not a guarantee of forensic erasure; OS/storage tools govern that.

To report a security problem, follow the [security policy](../SECURITY.md).
