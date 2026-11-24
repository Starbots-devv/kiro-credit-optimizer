---
name: kiro-credit-optimizer
description: Plan Kiro credit budgets, record usage snapshots, compare observed spending with allocations, and reduce repeated agent work. Use before a scoped development task or when investigating credit waste, budget drift, model strategy, or an engineering handoff.
license: Apache-2.0
metadata:
  author: Starbots
  version: "0.1.0"
---

# Kiro Credit Optimizer

Complete engineering work with less avoidable consumption. Necessary security, integrity and correctness checks always take priority over credit savings.

Basic planning needs no tools or network. The optional Starbots CLI requires Python 3.11+.

## Before work

1. State the objective, scope boundaries and acceptance checks. Reuse relevant repository instructions and previous decisions; search narrowly before opening whole directories.
2. Ask whether an existing private budget and recent official balance are available. Never guess a balance, subscription, billing rate or account credential. Do not require a budget to give planning guidance.
3. For deterministic tracking, first read [references/cli.md](references/cli.md). Verify the CLI is installed before invoking it. Importing this skill does **not** install the CLI.
4. Use the least costly available model capable of meeting the acceptance criteria. Consult the user's current Kiro model selector and official credit rules; do not assume model names or multipliers remain valid.
5. Prefer local deterministic tools for search, calculation, formatting and verification. Add agents only for clearly independent work whose value exceeds duplicated context and coordination cost.
6. Read [references/workflow.md](references/workflow.md) for estimation or a multi-phase task. Label estimates and low confidence explicitly. Agree on escalation points before expensive work.

## During work

- Stay within scope. Reuse tool results and completed diagnostics. Investigate the cause of a failure before another attempt.
- Record only authorized balances or reviewed measurements. Read [references/measurements.md](references/measurements.md) before recording or attributing usage.
- Account differences include concurrent activity. Never claim project attribution without explicit confirmation that the entire interval had exclusive account use.
- Thresholds are advisory. If consumption drifts, explain the evidence and revise scope, context or model strategy. This skill cannot block Kiro billing or switch models automatically.
- Never reduce required tests to satisfy a budget. Escalate the budget or scope decision when quality and available credits conflict.

## After work

- Report the actual verification outcome and known scope changes. Record an ending balance only if available; otherwise report usage as unknown.
- Attribute an interval only when its provenance and exclusivity are established. Mark a complete task verified only after necessary checks have passed.
- Compare attributed usage with the estimate, including retries and uncertainty. Do not report a savings percentage without comparable baseline evidence.
- Leave a brief handoff when another session is needed: decisions, relevant files, completed checks, pending work and budget observations. Keep private balances and notes out of public commits.

## Boundaries

No telemetry, credential extraction, private billing endpoint calls, automatic session scraping, background services, token-to-credit conversion, hard-limit enforcement or guaranteed savings. Local history is sensitive. User authorization governs file changes, installs and network access.
