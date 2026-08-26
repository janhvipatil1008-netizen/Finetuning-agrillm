"""Pytest bootstrap: make `src/` importable as top-level modules.

Tests import `schema`, `scope` and `freeze_check` directly rather than as
`src.schema`, so the source directory goes on sys.path before collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
