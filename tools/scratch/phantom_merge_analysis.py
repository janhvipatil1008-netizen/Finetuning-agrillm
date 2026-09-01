# Scratch: pre-merge verification of every Step 2b candidate against the
# approved Step B rules. Prints everything; writes nothing.
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"

d = json.loads((INTERIM / "phase3_step2b_phantom.json").read_text(encoding="utf-8"))

def sect(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)

# ---- 1. every candidate, classified under the approved rules ----
sect("1. ALL 57 CANDIDATES, PROPOSED DISPOSITION")
for fn, f in d["files"].items():
    short = fn.split("_2026")[0]
    for grp in ("all_dose_empty", "partial_dose_empty"):
        for c in f[grp]:
            own = c["own_columns"]
            has_crop = "crop" in own
            if has_crop and c["page"] == "32" and short == "insecticides":
                act = "ITEM-3 CROP-WRAP"
            elif has_crop:
                act = "EXCLUDE (own crop, genuine)"
            elif len(own) == 1:
                act = f"MERGE single -> {own[0]}"
            else:
                act = f"?? multi {own}"
            print(f"{short:16s} p{c['page']:>3} r{c['row_index']:>2} "
                  f"cls={'ALL' if grp=='all_dose_empty' else 'PART'} "
                  f"nseg={c['n_segments']} own={own} :: {act}")

# ---- 2. merge pairs in full: fragment vs parent cell content ----
sect("2. MERGE PAIRS (fragment text vs parent's target cell)")
for fn, f in d["files"].items():
    short = fn.split("_2026")[0]
    for grp in ("all_dose_empty", "partial_dose_empty"):
        for c in f[grp]:
            own = c["own_columns"]
            if "crop" in own:
                continue
            p = c["prev"]
            print(f"\n--- {short} p{c['page']} r{c['row_index']} own={own} "
                  f"prev=p{p['page']} r{p['row_index']} kind={p['assignment_kind']}")
            segs = c["raw_row_text"].split(" || ")
            for col, seg in zip(own, segs):
                print(f"    frag[{col:18s}] = {seg!r}")
            if len(segs) != len(own):
                print(f"    !! segment/own mismatch: {len(segs)} segs, {len(own)} own")
            for col in own:
                print(f"    parent.{col:18s} = {p.get(col, '<missing>')!r}")
            print(f"    parent.method       = {p.get('method','')!r}")
            print(f"    parent.dose_form    = {p.get('dose_formulation','')!r}")

# ---- 3. p32 crop-wrap: successors' crop values ----
sect("3. insecticides p32: crop carry below the phantom")
with open(INTERIM / "insecticides_20260331_raw.csv", encoding="utf-8") as fh:
    ins = list(csv.DictReader(fh))
for i, r in enumerate(ins):
    if r["source_page"] in ("31", "32", "33"):
        print(f"  idx={i} p{r['source_page']} r{r['source_row_index']:>2} "
              f"kind={r['assignment_kind']:16s} crop={r['crop']!r:.50} "
              f"raw={r['raw_row_text']!r:.60}")

# ---- 4. quarantine.csv, for the p28 parent ----
sect("4. quarantine.csv (full)")
with open(INTERIM / "quarantine.csv", encoding="utf-8") as fh:
    qrows = list(csv.DictReader(fh))
print("columns:", list(qrows[0].keys()) if qrows else "EMPTY")
for r in qrows:
    print(f"  {r.get('source_file','?'):18.18s} p{r.get('source_page','?'):>3} "
          f"r{r.get('source_row_index','?'):>2} reason={r.get('reason','?'):18.18s} "
          f"raw={r.get('raw_row_text','')!r:.90}")

# ---- 5. the 7 questionable no-own-crop partials, full prev ----
sect("5. NO-OWN-CROP MULTI-SEGMENT PARTIALS (genuine or wrap?)")
for fn, f in d["files"].items():
    short = fn.split("_2026")[0]
    for c in f["partial_dose_empty"]:
        own = c["own_columns"]
        if "crop" in own or len(own) == 1:
            continue
        p = c["prev"]
        print(f"\n--- {short} p{c['page']} r{c['row_index']} own={own}")
        print(f"    THIS raw: {c['raw_row_text']!r}")
        print(f"    PREV p{p['page']} r{p['row_index']} kind={p['assignment_kind']}")
        print(f"    PREV raw: {p['raw_row_text']!r}")
        print(f"    PREV phi={p['waiting_period_phi']!r} dil={p['dilution_water']!r} "
              f"ai={p['dose_ai']!r} form={p['dose_formulation']!r}")

# ---- 6. per-file counts for expected totals ----
sect("6. RAW/QUARANTINE COUNTS")
tot = 0
for fn in d["files"]:
    with open(INTERIM / fn, encoding="utf-8") as fh:
        n = sum(1 for _ in csv.DictReader(fh))
    tot += n
    print(f"  {fn}: {n} raw rows")
print(f"  TOTAL raw: {tot}")
print(f"  quarantine: {len(qrows)} rows")
