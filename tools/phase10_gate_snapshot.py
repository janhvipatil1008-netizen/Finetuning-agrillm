"""phase10_gate_snapshot.py — pin gate/filter-mode verdicts before the
score-mode change of Phase 10 Step A.

Phase 10 changes `verify()` in SCORE mode only: a schema-valid answer with an
empty `chemical_options` on an ANSWERABLE item now enters C1/C2/C3 as 0.0
misses instead of leaving them out of the denominator. Gate mode filtered the
5,629 Phase 8 SFT examples and filter mode is the inference safety net, so
neither may move by a byte.

This script was run ONCE, against the pre-change verify.py, to record what
gate and filter mode returned on a deterministic sample of benchmark items.
`tests/test_verify.py::test_gate_and_filter_modes_are_byte_identical_to_the_
pre_phase10_snapshot` replays the same inputs and asserts equality with the
recorded JSON. Re-running this script after the change would overwrite the
evidence with a tautology — do not, unless gate mode is deliberately being
changed and the report says so.

Sample: every 5th item of data/final/bench.jsonl (100 items), scored in gate
and filter mode as (a) its gold advisory and (b) the gold advisory with
`chemical_options` and `likely_causes` emptied — the exact shape whose
score-mode result changes. The ban list is the test fixture list from
tests/test_verify.py so the snapshot matches what the test fixture loads.

Output: tests/fixtures/phase10_gate_filter_snapshot.json
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

BENCH = ROOT / "data" / "final" / "bench.jsonl"
OUT = ROOT / "tests" / "fixtures" / "phase10_gate_filter_snapshot.json"
SAMPLE_STEP = 5
MODES = ("gate", "filter")


def emptied(gold: dict) -> dict:
    g = json.loads(json.dumps(gold))
    g["chemical_options"] = []
    g["likely_causes"] = []
    return g


def record(result) -> dict:
    return {
        "passed": result.passed,
        "total": result.total,
        "gates": result.gates,
        "checks": result.checks,
        "failures": result.failures,
        "excluded": result.excluded,
        "exclusion_reason": result.exclusion_reason,
        "ambiguous": list(result.ambiguous),
        "answerability": (result.answerability.value
                          if result.answerability else None),
    }


def snapshot(verify_mod, resources, items: list[dict]) -> dict:
    out = {}
    for it in items:
        ctx = verify_mod.VerifyContext(
            resources=resources, crop_slug=it["crop_slug"],
            pest_query=it["canonical_pest"])
        entry = {}
        for variant, payload in (("gold", it["gold_advisory"]),
                                 ("emptied", emptied(it["gold_advisory"]))):
            text = json.dumps(payload)
            for mode in MODES:
                entry[f"{variant}/{mode}"] = record(
                    verify_mod.verify(text, ctx, mode))
        out[it["item_id"]] = entry
    return out


def main() -> None:
    from test_verify import BAN_CSV
    with tempfile.TemporaryDirectory() as td:
        ban = Path(td) / "restricted_ai.csv"
        ban.write_text(BAN_CSV, encoding="utf-8")
        os.environ["AGRI_RESTRICTED_AI"] = str(ban)
        for name in ("verify", "restricted_ai"):
            sys.modules.pop(name, None)
        verify_mod = importlib.import_module("verify")
        resources = verify_mod.VerifyResources.load()

        with open(BENCH, encoding="utf-8") as f:
            items = [json.loads(l) for l in f if l.strip()]
        sample = items[::SAMPLE_STEP]
        snap = snapshot(verify_mod, resources, sample)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"sample_step": SAMPLE_STEP,
                               "n_items": len(sample),
                               "modes": list(MODES),
                               "results": snap},
                              indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    ans = sum(1 for e in snap.values()
              if e["gold/gate"]["answerability"] == "ANSWERABLE")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(sample)} items, "
          f"{ans} ANSWERABLE, {len(sample) * 4} verdicts")


if __name__ == "__main__":
    main()
