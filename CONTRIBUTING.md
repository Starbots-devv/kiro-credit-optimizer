# Contributing

Keep the runtime local, small and dependency-free. Public docs, comments and CLI messages use English. Preserve Apache 2.0 and any legitimate third-party notices.

## Development setup

From the repository root with Python 3.11+:

```bash
python -m venv .venv
```

Use `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on macOS/Linux for the following commands:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-build-isolation --no-deps -e .
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
python scripts/check_repository.py
python examples/demo.py
python -m build --no-isolation
```

The install commands may access package indexes. The tests and ordinary runtime are offline. Tests can run without installation by setting `PYTHONPATH=src` (PowerShell: `$env:PYTHONPATH = 'src'`). Ruff, build and YAML tooling are development dependencies only.

## Changes and review

Use synthetic fixtures. Add a regression test for changed behavior, including failure modes where relevant. Keep exact amounts, timezone boundaries, source provenance and account/project separation intact. A change to a storage format needs an explicit compatibility story; never reset user history to simplify a migration.

Review every staged file for private identifiers, billing data, exports, credentials and generated caches. Keep documentation commands consistent with the parser. Explain the resulting behavior and validations in pull requests. Do not claim live Kiro compatibility or measured savings based on synthetic tests.

Review licenses and include required attribution before copying third-party code. Report security problems privately as described in [SECURITY.md](SECURITY.md), not in public issues.
