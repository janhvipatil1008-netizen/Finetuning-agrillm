# Phase 3, Step 2 — Extract (raw CSVs)

Raw extraction only. No normalisation, no dose parsing, no label_db. Outputs (`data/interim/*.csv`) are gitignored, as with every prior phase's intermediate cache — this report and `tools/phase3_step2_extract.py` are the committed record; re-running the script regenerates the CSVs from the source PDFs.

Deliverables: `data/interim/<name>_raw.csv` (one per file), `data/interim/quarantine.csv`, `data/interim/verify_sample.csv` (25 rows for manual spot-check).

## Row counts and the hard assertion

| file | raw CSV rows | quarantine rows | total source rows |
|---|---|---|---|
| `insecticides_20260331.pdf` | 2048 | 3 | 2051 |
| `fungicides_20260331.pdf` | 1273 | 1 | 1274 |
| `bio_insecticides_20260331.pdf` | 294 | 0 | 294 |
| `bio_fungicides_20260331.pdf` | 147 | 0 | 147 |
| **total** | **3762** | **4** | **3766** |

**HARD ASSERTION: raw (3762) + quarantine (4) = 3766 total source rows. PASSED** — every row camelot returned across all four files' lattice tables lands in exactly one of the two output files, verified by the extraction script itself (it exits non-zero on mismatch, not just reported here after the fact).

## Quarantine, by reason code

| reason_code | rows | what |
|---|---|---|
| `cols_unresolved` | 3 | row-local segmentation found >6 real segments — the Aluminum Phosphide fumigation sub-table (insecticides p27), a genuinely 7-field schema (Step 1b) |
| `footnote_unresolved` | 0 | a marker with no registry match, superseded by `unresolved_marker=True` for the one case that actually exists (FYM*) — see below |
| `truncated_cell` | 1 | known character-loss defect from the phase 2b audit (fungicides p38, wrapped dilution cell missing its last line) — hardcoded, not guessed |
| `section_ambiguous` | 0 | a row whose own y-position couldn't be placed above/below a known section split — none occurred |

`footnote_unresolved` is 0 by design, not by omission: the 32 `FYM*` rows are the only unresolvable-marker case in this corpus (confirmed in pre-work — no definition exists anywhere in either bio file), and you explicitly said keep those, not quarantine them. The reason code stays implemented for a future corpus that might need it; nothing in this run does.

Full quarantine list:

| file | page | table | row | reason | raw_row_text |
|---|---|---|---|---|---|
| `insecticides_20260331.pdf` | 27 | 26 | 15 | cols_unresolved | Crop \|\| Common  name of the  pest \|\| Cond. \|\| Weight of volume \|\| Exposure  period |
| `insecticides_20260331.pdf` | 27 | 26 | 16 | cols_unresolved | Stored whole  cereals  Millets Pulses \|\| Rice weevil,  Lesser grain  Borer,  Khapra  Bee |
| `insecticides_20260331.pdf` | 27 | 26 | 17 | cols_unresolved | Go down  fumigation \|\| Rice weevil,  Lesser grain  Borer, Khapra \|\| Airtight  cover \| |
| `fungicides_20260331.pdf` | 38 | 36 | 0 | truncated_cell | Apple \|\| Marssonina Leaf  blotch  (premature leaf  fall) \|\| 3.22 gram/10 L  of water \ |

## `phi_cell_present` breakdown

New requirement this step: a bool on every row recording whether a ruled PHI cell exists at all (even blank), independent of whether this row's own PHI value is populated. Computed **content-first**: if any row in the table has a non-blank resolved PHI value, the column obviously exists — no geometry needed. Only when EVERY row in the table is PHI-blank does it fall back to the geometric test (a ruled column edge near the calibrated PHI-band start).

A geometry-first version was tried and rejected: insecticides p2 — one of the file's own CALIBRATION source pages, with ordinary populated PHI values on every row — has its own dilution/PHI cut 27.9pt from the calibrated median, just outside a 25pt tolerance, so pure geometry called it "absent" while every row's own content plainly said otherwise. That version showed **243** `False` rows spread across 15 pages, most of them ordinary populated tables. Content-first drops that to **24** `False` rows across exactly the **2** tables Step 1b hand-verified as genuinely ABSENT — insecticides p7 (10 rows) and bio_insecticides p10 (14 rows) — and nothing else. The other 4 tables Step 1b called PRESENT-AND-EMPTY (insecticides p52, fungicides p31, bio_fungicides p11 and p16) all correctly land on `True`.

| phi_cell_present | rows | meaning |
|---|---|---|
| `True` | 3307 | ruled PHI cell exists — content present or a confirmed present-and-empty table |
| `False` | 24 | no ruled PHI cell anywhere in this table — insecticides p7, bio_insecticides p10 only |
| (blank) | 431 | non-crop-advisory row — no calibrated grid exists for this schema, concept doesn't apply |

## `unresolved_marker` and `footnote_text`

- `unresolved_marker=True`: **32 rows** — exactly the 32 FYM* rows confirmed in pre-work (20 bio_insecticides, 12 bio_fungicides). Cell text kept verbatim, asterisk included, not quarantined.
- `footnote_text` populated: **5 rows** — the fungicides p4 (4 rows: Apple, Cherry, Citrus x2) and p77 (1 row: Wheat/Sedaxane combo) markers, resolved against p83's endnotes.

## Bugs found and fixed while building this

Neither of these was caught by the hard assertion (row counts balanced throughout) — both were caught by checking specific rows' actual output against what was already known to be true, not by trusting that a green assertion meant the extraction was correct.

1. **Footnote registry, marker misassignment.** A `\*{1,4}` regex backtracks whenever the text after a shorter marker also starts with `*`. This corpus hits that twice: bio_fungicides p20's bare `***` parsed as marker=`**`+body=`*`, and fungicides p83's `** In case of...` (space before the word) parsed as marker=`*`+body=`* In case of...`. Fixed by counting the leading `*` run manually instead of matching it with a regex.

2. **Footnote registry, page-1 contamination.** bio_insecticides' page-1 disclaimer begins with a bare `*` and flows straight into the contents list with no blank line. The continuation-absorption logic swallowed the whole block as one `*` "definition", which — being that file's only `*` entry — then resolved all 20 of its FYM* rows against disclaimer text instead of leaving them `unresolved_marker=True` as you'd just confirmed. Caught by reading the FYM rows' actual `footnote_text` output, not by inspecting the registry dict in isolation. Fixed by skipping page 1 outright — no table page ever needs a footnote defined there.

3. **`phi_cell_present`, geometric false negatives.** See above — 243 false `False`s dropped to the correct 24 by checking row content before falling back to geometry.

## Forward-fill spot check (insecticides p10 -> p11)

| page | crop | pest_or_disease | active_ingredient |
|---|---|---|---|
| 10 | Citrus | Leaf miner | Carbofuran 03%CG |
| 10 | Maize | Stem borer, Shoot fly, Thrips | Carbofuran 03%CG |
| 10 | Paddy(Rice) | Brown plant hopper, Gall  midge, Stem borer,  | Carbofuran 03%CG |
| 11 | Paddy(Rice) | hopper, Hispa | Carbofuran 03%CG |
| 11 | Paddy(Rice) | Nematodes | Carbofuran 03%CG |
| 11 | Mustard | Mustard leaf miner | Carbofuran 03%CG |

`crop` ("Paddy(Rice)") and `active_ingredient` ("Carbofuran 03%CG") both survive the page break correctly, matching phase 2b's documented p10->p11 case.

## Non-crop-advisory rows

No calibrated grid exists for public-health / household / locust schemas (Step 1/1b validated crop-advisory subsections only — those sections have genuinely different logical columns). Every row from those sections is still in the raw CSV, tagged with its row-level section/subsection (row-level, not page-level, on the three known boundary pages), but with the six crop-advisory semantic columns and `phi_cell_present` left blank and `raw_row_text` populated instead — the row-local real-rule segments, joined verbatim, schema-agnostic. Nothing from these sections is dropped or quarantined for being non-crop-advisory.

| section | rows |
|---|---|
| crop-advisory | 3331 |
| household | 267 |
| public-health | 154 |
| locust | 10 |

## Not done here

No cleaning, no unit conversion, no dose parsing (`parse_phi` is not called — the `waiting_period_phi` column holds the raw cell text verbatim, e.g. `"2 weeks"`, not `14`), no label_db. That is Phase 4.

