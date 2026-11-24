"""Run a reviewed source checkout without installation or runtime dependencies."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from starbots_kco.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
