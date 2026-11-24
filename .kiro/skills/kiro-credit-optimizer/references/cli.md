# Optional deterministic CLI

The skill works as guidance alone. To track credits, install the separate Python 3.11+ tool from a reviewed checkout of [Kiro Credit Optimizer](https://github.com/Starbots-devv/kiro-credit-optimizer). No package is published to PyPI in this release.

```powershell
git clone https://github.com/Starbots-devv/kiro-credit-optimizer.git
Set-Location .\kiro-credit-optimizer
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\starbots-kco.exe --version
```

Use Python 3.11 or later. On macOS/Linux substitute `python3`, `.venv/bin/python` and `.venv/bin/starbots-kco`. A reviewed checkout can also run offline with `python /path/to/kco.py`; installation may download the packaging toolchain.

Run from the target workspace, with an absolute executable path if needed. The default data location is `.kiro-credits/` under the current working directory. `--data-dir` must appear **before** the command. Confirm this directory is ignored by the target repository before recording real data.

```text
starbots-kco init --project example-app --monthly 2000 --budget 1000 --reserve 100
starbots-kco doctor
starbots-kco config --json
starbots-kco estimate --task-type bugfix --complexity small --retries 1 --json
starbots-kco snapshot --balance 1800 --reference "Kiro /usage, user entered"
starbots-kco snapshot --balance 1700 --reference "Kiro /usage, user entered"
starbots-kco report --json
```

The numbers above are synthetic. Snapshot IDs are returned by the CLI. Snapshot labels are context, never attribution. If the user confirms exclusive account use over the entire interval, `starbots-kco claim 1 2 --phase implementation --exclusive-account` attributes that interval. Substitute the actual IDs. Do not add `--verified` unless a complete task is represented and its necessary checks passed.

Read the [usage guide](https://github.com/Starbots-devv/kiro-credit-optimizer/blob/main/docs/USAGE.md) for task/session allocations, date rules, exports and exact measurement limitations.
