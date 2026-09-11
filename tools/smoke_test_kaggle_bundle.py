"""smoke_test_kaggle_bundle.py -- prove kaggle_upload/ works standalone.

Imports verify from the FLATTENED bundle (kaggle_upload/ at sys.path[0],
src/ never on the path), loads every resource through kaggle_paths.DATA_DIR,
and scores 3 gold advisories from bench.jsonl -- already-verified answers,
so anything below total == 1.0 means the bundle is broken.

Run after tools/bundle_for_kaggle.py:  python tools/smoke_test_kaggle_bundle.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1] / "kaggle_upload"
if not BUNDLE.exists():
    sys.exit("kaggle_upload/ not found -- run tools/bundle_for_kaggle.py first")
sys.path.insert(0, str(BUNDLE))

# kaggle_paths must come first: it sets AGRI_RESTRICTED_AI, which verify.py
# needs at import (the ban list loads when the module loads, deliberately).
import kaggle_paths  # noqa: E402

DATA_DIR = kaggle_paths.DATA_DIR
print(f"DATA_DIR resolved to: {DATA_DIR}")

from pest_matcher import load_table  # noqa: E402
from verify import (  # noqa: E402
    RESTRICTED_AI, LabelDB, VerifyContext, VerifyResources,
    load_contradictions, load_label_db, verify,
)

assert Path(sys.modules["verify"].__file__).parent == BUNDLE, \
    "verify was imported from outside the bundle"

df = load_label_db(DATA_DIR / "label_db.parquet")
print(f"label_db loaded: {len(df)} rows")
table = load_table(DATA_DIR / "pest_synonym_table.csv")
print(f"pest_synonym_table loaded: {len(table.rows)} rows")
print(f"restricted_ai loaded: {len(RESTRICTED_AI)} rows from {RESTRICTED_AI.source}")
assert Path(RESTRICTED_AI.source).parent == BUNDLE, \
    "ban list was loaded from outside the bundle (AGRI_RESTRICTED_AI not honoured)"

resources = VerifyResources(
    label_db=LabelDB(df, table,
                     load_contradictions(DATA_DIR / "known_contradictions.csv")),
    table=table, restricted=RESTRICTED_AI)

# 3 DOSE items: the only bench kind whose gold advisory exercises the full
# gate + graded-check path (chemistry, dose, PHI) rather than an empty answer.
items = []
with open(DATA_DIR / "bench.jsonl", encoding="utf-8") as fh:
    for line in fh:
        rec = json.loads(line)
        if rec["kind"] == "DOSE":
            items.append(rec)
        if len(items) == 3:
            break

failed = False
for rec in items:
    ctx = VerifyContext(resources, rec["crop_slug"],
                        pest_query=rec["canonical_pest"])
    r = verify(json.dumps(rec["gold_advisory"]), ctx, mode="score")
    status = "OK " if r.total == 1.0 and not r.excluded else "FAIL"
    print(f"  [{status}] {rec['item_id']}: total={r.total} passed={r.passed} "
          f"excluded={r.excluded} gates_failed="
          f"{[k for k, v in r.gates.items() if not v]} failures={r.failures}")
    if r.total != 1.0 or r.excluded:
        failed = True

sys.exit(1 if failed else 0)
