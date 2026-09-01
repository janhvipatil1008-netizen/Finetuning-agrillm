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
#
# schema.py RE-FROZEN 2026-08-31 (Phase 6). Comment-only: the `per_acre`
# member of `Basis` claimed label_db had "already converted from per_ha",
# which was false — label_db stored per_ha exclusively. Rather than weaken the
# comment, the conversion was implemented (src/dose_units.py adds four derived
# per-acre columns) and the comment now describes what the data holds. One
# line, inside a comment; Basis members, field names and validators are
# byte-for-byte what they were.
#
# schema.py RE-FROZEN AGAIN 2026-09-01 (Phase 6). Two SEMANTIC additions,
# batched deliberately as the LAST break before training-data generation:
#   * ChemicalOption.phi_not_applicable — phi_days=None meant both "unknown"
#     and "does not apply", so the old invariant forced an affirmatively wrong
#     escalation on the 16 seed-dresser rows.
#   * Basis gains "unstated" — refuse-to-guess had no expression, leaving 42
#     dose-less rows colliding with 10 genuine prose doses.
# See SOURCES.md -> "Re-freeze 2026-09-01" for the full rationale and the
# deliberate omissions. After training-data generation starts, schema.py's own
# invalidation clause fires and a further change costs the dataset.
FROZEN_SHA256 = {
    "schema.py": "8521721c7abe216984e627f0ed54d47f897ffdaf775fc03677828afb9244f810",
    "system_prompt.txt": "8b0a4b78c02a8c0286d3ee82acc7d47b73c4cb903a0c62b5f6fc1c1ca352b4a1",
}

# Superseded hashes, kept so an older checkout can be identified rather than
# merely reported as "not matching". Never used for validation.
SUPERSEDED_SHA256 = {
    "schema.py": {
        "53f68176d62820e4eb589bfaebc83ea2ee060ed84e0860716e014a9bf29af42f":
            "Act 2 freeze, 2026-08-27 — pre per-acre comment correction",
        "13c6d7b0f2d051620614e010f638dd34497751d24a8f6d3187d9145fee180dec":
            "Phase 6 freeze, 2026-08-31 — before phi_not_applicable and "
            "Basis 'unstated'",
    },
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
            known = SUPERSEDED_SHA256.get(name, {}).get(actual)
            if known:
                raise FrozenArtifactError(
                    f"{name} matches a SUPERSEDED freeze, not the current one.\n"
                    f"  on disk : {actual}\n"
                    f"            ({known})\n"
                    f"  expected: {expected}\n"
                    f"This is an out-of-date checkout of a known version, not a "
                    f"corrupted or edited file. Update the working tree rather "
                    f"than re-freezing."
                )
            raise FrozenArtifactError(
                f"{name} is no longer byte-identical to the recorded freeze.\n"
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
    "SUPERSEDED_SHA256",
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
