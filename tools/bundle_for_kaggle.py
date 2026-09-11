"""bundle_for_kaggle.py -- Phase 10 Step 1: flatten everything Kaggle needs.

Copies data, code and config into kaggle_upload/ at the TOP LEVEL (no
subdirectories -- Kaggle datasets do not preserve directory structure well),
and writes kaggle_paths.py, a shim that resolves the data directory both on
Kaggle (/kaggle/input/<dataset>/) and locally (beside the script).

Two deliberate departures from a naive file list:

- label_db.parquet is bundled IN ADDITION to label_db.csv.
  verify.load_label_db refuses a .csv path: phi_days degrades from nullable
  Int64 to float64 through CSV, collapsing the 0-vs-None distinction
  parse_phi.py exists to preserve. The CSV still ships (human-inspectable,
  and kaggle_paths probes for it to find the dataset mount); the parquet is
  what verify actually reads.

- The code set is the traced import graph of verify.py, not a guessed list.
  _trace_imports() walks `import X` / `from X import ...` statements over
  src/*.py starting from the seed modules, so a future import added to
  verify.py lands in the bundle on the next run instead of breaking Kaggle.
  (There is no normalise_ai.py module -- normalise_ai is a function inside
  verify.py; the traced graph pulls in restricted_ai.py, which the naive
  list misses and without which verify.py cannot even be imported.)

Run from anywhere:  python tools/bundle_for_kaggle.py
Then verify with:   python tools/smoke_test_kaggle_bundle.py
"""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FINAL = ROOT / "data" / "final"
OUT = ROOT / "kaggle_upload"

DATA_FILES = [
    "sft_train.jsonl",
    "sft_test.jsonl",
    "bench.jsonl",
    "label_db.csv",
    "label_db.parquet",       # what verify.load_label_db actually accepts
    "pest_synonym_table.csv",
    "restricted_ai.csv",
    "known_contradictions.csv",
]

# Modules the task requires by name; the tracer closes over their imports.
# application_method.py is seeded too: bench items carry no application_method
# field, so the Kaggle eval script must re-extract it from query_text the way
# generate_sft.py did (extract_method), or gate-mode candidate narrowing
# diverges from generation.
SEED_MODULES = [
    "verify", "schema", "scope", "pest_matcher", "dose_parser",
    "parse_phi", "crop_mapper", "formulation_resolver", "application_method",
]

CONFIG_FILES = ["system_prompt.txt"]

KAGGLE_PATHS = '''\
# kaggle_paths.py -- path resolution for the flattened Kaggle layout.
#
# IMPORT THIS BEFORE verify: restricted_ai.py loads the ban list at import
# time from a repo-relative default that does not exist in the flat layout,
# and the AGRI_RESTRICTED_AI env var set below is its supported override.
import os
from pathlib import Path

# On Kaggle, the dataset is mounted at /kaggle/input/<dataset-name>/
# Locally, files sit beside this script.
KAGGLE_INPUT = Path("/kaggle/input")


def data_dir() -> Path:
    if KAGGLE_INPUT.exists():
        # find the first subdirectory containing label_db.csv
        for d in KAGGLE_INPUT.iterdir():
            if (d / "label_db.csv").exists():
                return d
    return Path(__file__).parent


DATA_DIR = data_dir()

os.environ.setdefault("AGRI_RESTRICTED_AI", str(DATA_DIR / "restricted_ai.csv"))
'''


def _trace_imports(seeds: list[str]) -> list[str]:
    """Closure of `import`/`from ... import` over src/*.py, seeds included."""
    local = {p.stem for p in SRC.glob("*.py")}
    missing = [s for s in seeds if s not in local]
    if missing:
        raise SystemExit(f"seed module(s) not found in src/: {missing}")
    seen: set[str] = set()
    queue = list(seeds)
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        seen.add(mod)
        tree = ast.parse((SRC / f"{mod}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            queue += [n for n in names if n in local and n not in seen]
    return sorted(seen)


def main() -> None:
    OUT.mkdir(exist_ok=True)

    copies: list[tuple[Path, str]] = []
    copies += [(FINAL / f, f) for f in DATA_FILES]
    copies += [(SRC / f"{m}.py", f"{m}.py") for m in _trace_imports(SEED_MODULES)]
    copies += [(SRC / f, f) for f in CONFIG_FILES]

    absent = [str(src) for src, _ in copies if not src.exists()]
    if absent:
        sys.exit("missing source file(s) -- nothing copied:\n  " + "\n  ".join(absent))

    for src, name in copies:
        shutil.copy2(src, OUT / name)

    (OUT / "kaggle_paths.py").write_text(KAGGLE_PATHS, encoding="utf-8")

    bundled = sorted(OUT.iterdir())
    total = sum(p.stat().st_size for p in bundled)
    width = max(len(p.name) for p in bundled)
    for p in bundled:
        print(f"  {p.name:<{width}}  {p.stat().st_size:>10,} bytes")
    print(f"\n{len(bundled)} files, {total:,} bytes "
          f"({total / 1024 / 1024:.2f} MB) -> {OUT}")


if __name__ == "__main__":
    main()
