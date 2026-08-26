"""Byte-level freeze guard for the output schema and the system prompt.

Act 2 froze `src/schema.py` and `src/system_prompt.txt`. Both are load-bearing
for every downstream stage: the schema decides which samples are allowed into
`data/final/`, and the prompt must be byte-identical between the authoring
machine (Windows) and any Linux training run. A silent edit — or a line-ending
rewrite on checkout — would quietly invalidate every dataset built after it.

Call `assert_frozen()` first in any script that loads the prompt or the schema.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_SRC = Path(__file__).resolve().parent

SCHEMA_PATH = _SRC / "schema.py"
SYSTEM_PROMPT_PATH = _SRC / "system_prompt.txt"

# Recorded 2026-08-27 (Act 2, reviewed — supersedes the same day's pre-review
# draft; see archive/superseded_draft/README.md), with `src/schema.py -text`
# and `src/system_prompt.txt -text` in .gitattributes. See SOURCES.md ->
# "Frozen artifacts".
FROZEN_SHA256 = {
    "schema.py": "53f68176d62820e4eb589bfaebc83ea2ee060ed84e0860716e014a9bf29af42f",
    "system_prompt.txt": "8b0a4b78c02a8c0286d3ee82acc7d47b73c4cb903a0c62b5f6fc1c1ca352b4a1",
}


class FrozenArtifactError(RuntimeError):
    """Raised when a frozen artifact no longer matches its recorded SHA-256."""


def sha256_of(path: Path) -> str:
    """Return the hex SHA-256 of `path`, hashed as raw bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_frozen() -> None:
    """Recompute both frozen hashes and raise if either has drifted.

    Raises:
        FrozenArtifactError: if a frozen file is missing, or its bytes no
            longer hash to the value recorded above.
    """
    for name, expected in FROZEN_SHA256.items():
        path = _SRC / name
        if not path.exists():
            raise FrozenArtifactError(f"frozen artifact is missing: {path}")

        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise FrozenArtifactError(
                f"{name} is no longer byte-identical to the Act 2 freeze.\n"
                f"  expected sha256: {expected}\n"
                f"  actual   sha256: {actual}\n"
                f"  actual size    : {len(data)} bytes\n"
                f"If the size grew by roughly the number of lines, git rewrote "
                f"the line endings on checkout — check .gitattributes. "
                f"Otherwise the file was edited: revert it, or re-freeze "
                f"deliberately and update SOURCES.md and FROZEN_SHA256."
            )


__all__ = [
    "FROZEN_SHA256",
    "FrozenArtifactError",
    "SCHEMA_PATH",
    "SYSTEM_PROMPT_PATH",
    "assert_frozen",
    "sha256_of",
]


if __name__ == "__main__":
    assert_frozen()
    for _name, _expected in FROZEN_SHA256.items():
        print(f"ok  {_name}  {_expected}")
