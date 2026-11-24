# Measurement boundary

Sources are user-supplied provenance labels, not independently authenticated by this tool:

| Source | Meaning |
|---|---|
| `manual-official` | A person transcribed an official account balance, such as `/usage`. |
| `official-report` | A balance was taken from an authorized official report; reference the report without storing its private contents. |
| `authorized-local` | A reviewed local tool supplied an actual credit balance. Its implementation format may be unstable. Token counts and dollar estimates are not balances. |

No source is collected automatically in v0.1. Estimates are produced separately and cannot be recorded as observations. A user-supplied label is not proof of billing accuracy.

Always compare the **same credit pool**. The default basis is monthly remaining credits; do not mix it with add-on balances, total combined credits, cumulative usage, tokens or currency. A pool change requires a new private data directory. Record timezone-aware timestamps and concise, non-sensitive references.

An interval is `[start, end)`. It must stay within one configured renewal cycle, have non-increasing balances throughout, and not overlap another attributed claim in the same ledger. Adjacent intervals may share an endpoint. A top-up or billing correction requires fresh baselines around the adjustment; never infer the hidden consumption.

Default account observations remain unattributed. Only use an exclusive-account claim after the user confirms no unrelated activity consumed credits during that interval. Snapshot phase/task/session tags do not establish this. Separate data directories cannot detect each other's overlaps. Use a single ledger per account/pool/workspace measurement exercise, and never sum independent exports as if they were deduplicated.

The CLI does not inspect Kiro authentication, prompts, responses, session databases, private APIs, cloud logs or project repositories. Never request credentials for basic use. Treat exports, labels, timestamps and notes as private.
