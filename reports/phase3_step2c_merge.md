# Phase 3, Step 2c — Phantom Continuation Merge

**49 phantom rows merged into their parents and dropped from the raw CSVs.**
Executed by `tools/phase3_step2c_merge.py` against the Step 2b diagnosis
(`reports/phase3_step2b_phantom.md`); every dropped row is preserved in full in
`data/interim/phase3_step2c_manifest.json` (gitignored), with the parent's
before/after cell text per append. `src/schema.py` untouched. The extractor's
CSVs are reborn WITH the phantoms on any re-extract — `phase3_step2c_merge.py`
must be re-run after every `phase3_step2_extract.py` run (it refuses to run
twice, and aborts before any write if the data has drifted from its frozen
49-row merge set).

## 1. Accounting — expected stated before running, asserted after

Restated hard assertion, per requirement:

```
source rows == raw + quarantine + merged-away fragments
3766        == 3703 + 14 + 49        (held on the actual run)
```

| file | raw before | merged away | raw after (expected) | raw after (actual) |
|---|---|---|---|---|
| insecticides | 2042 | 22 | 2020 | 2020 |
| fungicides | 1269 | 9 | 1260 | 1260 |
| bio_insecticides | 294 | 3 | 291 | 291 |
| bio_fungicides | 147 | 15 | 132 | 132 |
| **total** | **3752** | **49** | **3703** | **3703** |

Quarantine: **14 rows before, 14 after** — no row added or removed; exactly one
row's `raw_row_text` was extended (§4, insecticides p27 r17).

Merge count by row type: pest single 23 · method single 12 · dilution single 3
· dose_formulation single 2 · multi-column 7 · quarantine-parent 1 · crop-wrap 1.

Per-column appends (segments, not rows): pest_or_disease 29 · method 15 ·
dose_formulation 6 · dilution_water 6 · dose_ai 2 · waiting_period_phi 2 ·
crop 1 · quarantine raw_row_text 1.

## 2. Hard precondition — own-crop exclusion (requirement 1)

Ran BEFORE any merge, enforced by assertion in the script. Of the 57 Step 2b
candidates, **7 have a populated own-crop segment**:

* **6 excluded, untouched** — genuine rows: `bio_insecticides p10 r0` (the
  known case, asserted specifically), `insecticides p53`, `fungicides p17`,
  `p36`, `p42`, `p55`.
* **1 rerouted** — `insecticides p32 r0`, the crop wrap, merged only via the
  dedicated crop-wrap path (§5), never the generic column rule.

Also verified genuine and untouched: `insecticides p26` and `p75` — their
parents are complete (PHI filled, nothing dangling) and the rows carry their
own dose values (`Jassids, Aphids || 84 || 700 || 500`): second registered
claims under the same chemical, not tails.

## 3. The merge rule (requirement 2) — worked examples, one per column

Each fragment segment appends (single space, verbatim) to the SAME column of
the last data row of the previous page; the fragment's `raw_row_text` appends
to the parent's; the fragment row is dropped. Column-specific, never a
catch-all.

**PEST — insecticides p14 r0 → p13 r15** (dose cells untouched: `30 | 50 |
500-750 | 31`):

> `Pod borer (Helicoverpa armigera) Spotted pod borer (Maruca spp.)`
> ⊕ `Pod fly (Melanagromyza obtusa)`

**PEST — insecticides p69 r0 → p68 r13** (the dangling `Thrips:` gets its
species):

> `...American Bollworm: Helicoverpa armigera Thrips:` ⊕ `Thrips tabaci`

**METHOD — fungicides p33 r0 → p32 r2**: fragment
`the vascular bundles insides the seedlings. Spray: ...` appended to the
parent's `method` cell, which was empty — the prose HEAD sits in the parent's
`dose_formulation` (`Seeds treatment: Prepare streptocycline 40 ppm ...
penetrate`), where band assignment put it. Same-column append keeps both
rows' assignments raw: the merged row holds head in `dose_formulation`, tail
in `method`, full reading order in `raw_row_text`. Which cell "should" hold
prose is a Step 4 normalisation question the parent posed before this merge.
(Same shape on fungicides p31 and bio_fungicides p5/p8/p13/p14/p16/p19.)

**DILUTION — fungicides p16 r0 → p15 r11**:

> `As required depending upon crop stage And plant protection`
> ⊕ `equipment used`

(The same wrapped-dilution construction as the p38 `truncated_cell`
quarantine — this one recoverable because the tail survived on the next page.)

**DOSE_FORMULATION — fungicides p34 r0 → p33 r2**:

> `...covering two` ⊕ `rows on either side.`

## 4. Quarantine-parent case — insecticides p28 r0 (folded per approval)

Its raw-CSV predecessor is p27's column-header row: the true parent is the
**quarantined** Aluminum-Phosphide fumigation row p27 r17 (`Go down fumigation
|| Rice weevil, Lesser grain Borer, Khapra || ...` — cut mid-word; the
fragment opens `Beetle, Rust red flour beetle...` and its second segment
completes the aeration cell's `...followed by`). A 7-field-schema quarantine
row has no 6-band cells, so the fragment's `raw_row_text` was appended to the
quarantine row's `raw_row_text`. Quarantine count unchanged at 14.

## 5. Crop-wrap case — insecticides p32 r0 (requirement 3)

Handled by its own path because `crop` is the forward-fill anchor:

* `and coconut)` → parent p31 r22 crop:
  `For rodent control in field, storage and crops like rice, soybean and coconut)`
* `after14 days if problem persists.` → parent dilution:
  `At an interval of 5-10m in bait station or active burrow. Repeat the
  application after14 days if problem persists.`
* **Carry-leak assertion**, not assumption: the script asserts no later row
  carries the fragment's crop. Clean — the immediately following row is the
  `Flonicamid 50%WG` chemical header, which resets the carry, so zero rows
  ever inherited `and coconut)`.

## 6. The 5 wraps added beyond the originally approved set

Pre-merge verification showed Step 2b §5's "genuine" read was wrong for five
partial-class rows; approved for inclusion 2026-08-29. Evidence — the parent
cell each fragment completes:

| row | parent's dangling cell → fragment |
|---|---|
| insecticides p16 | form `750 –` → `1000`; pest `Mites` → `(Polyphagotarsonemus latus)`; PHI empty → `05` |
| insecticides p70 | ai `(200.5 + 19.5 –` → `(240.6 + 23.4)`; pest `Thrips, Mites and` → `Whitefly` |
| fungicides p78 | pest `Aphid,` → `Jassids, Whitefly, Fungal wilt and Root rot`; ai `1.25 (Sedaxane-` → `0.1+ Fludioxonil- 0.1+ Thiamethoxam- 1.05)` |
| bio_fungicides p6 | pest `Leaf and` → `neck blast (Pyricularia oryzae)`; form `10gm/kg` → `seed` |
| bio_fungicides p15 | pest `...f.sp.` → `lycopersici)`; PHI `Dilution in water-` → `500 liter/ha` (all four cells continue) |

The discriminator separating these from the genuine p26/p75: a wrap's parent
has dangling/incomplete cells that the fragment's cells textually complete; a
genuine row's parent is complete and the row carries its own value set.

## 7. Post-merge sweep

Re-running the Step 2b net on the merged CSVs finds five
first-row-of-page all-dose-empty data rows — all with `source_row_index` 1
(plus the protected bio_insecticides p10 r0). These are not phantoms: after
dropping an r0 fragment, the CSV-first row of that page is no longer the
PHYSICAL top row, and a page-break wrap can only ever be the physical r0.
They are ordinary prose/bio rows with blank dose cells, mid-page in the
source.

`data/interim/verify_sample.csv` predates this merge — regenerate or sample
directly from the merged raw CSVs when re-verifying.
