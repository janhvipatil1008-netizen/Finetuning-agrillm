# SOURCES.md — Raw Data Provenance

Raw data is **not committed** (see `.gitignore`). This file is the contract for
reproducing `data/raw/` from scratch. Every raw drop must be logged in the
inventory tables below before it is used downstream.

Directory convention:

```
data/raw/kcc/      # Kisan Call Centre farmer query transcripts
data/raw/cibrc/    # CIB&RC pesticide registration / label-claim registers
data/interim/      # cleaned + filtered intermediates (regenerable)
data/final/        # train / val / test splits shipped to fine-tuning
```

---

## Reproducing `data/interim/` from `data/raw/`

`data/interim/` is gitignored (regenerable, per the convention above) — the
CIB&RC registers below must already be in place per §1.1 before this runs.
The single official command:

```
python tools/run_phase3.py
```

This runs, in order, each as its own subprocess so no script's globals leak
into another's:

1. `phase3_step2_extract.py` — PDFs -> raw CSVs + `quarantine.csv`
2. `phase3_step2c_merge.py` — merges the 49 phantom continuation rows
   diagnosed in `reports/phase3_step2b_phantom.md` (a cell that wraps across
   a page break otherwise resurfaces as a fabricated label-claim row)
3. `phase3_step2e_fix_row7.py` — corrects the one quarantine-parent field
   merge documented in `reports/phase3_row7_check.md`

Every step's precondition is checked before it runs and aborts loudly, by
name, if unmet — e.g. step 3 refuses to run if step 2's manifest is missing,
rather than failing partway through with a stack trace. The pipeline is
idempotent: re-running it is safe, and an already-merged/already-fixed step
no-ops.

Not run by this command (one-time analysis, not part of reproducing the
data from a frozen set of rules): `phase3_step2b_phantom.py` /
`phase3_step2b_report.py` (the diagnosis that produced the frozen 49-row
merge set) and `phase3_step2d_verify_sample.py` (regenerates the hand-check
sample in `data/interim/verify_sample.csv`).

---

## 0. Licensing, attribution and redistribution

The CIB&RC registers below are **Government of India** publications, issued by the
Central Insecticides Board & Registration Committee (CIB&RC), Directorate of Plant
Protection, Quarantine & Storage, Department of Agriculture & Farmers Welfare,
Ministry of Agriculture & Farmers Welfare.

* **We do not redistribute the PDFs.** They are excluded from version control via
  `.gitignore` (`data/raw/`). Anyone reproducing this project must download them
  themselves from the official page recorded below.
* **We publish only derived data** (the normalised label database in
  `data/final/`) — never the source documents.
* **Attribution is mandatory** on any derived artefact: the label database, the
  training set, and any model output that quotes a dose or pre-harvest interval
  must be traceable to "CIB&RC, Major Uses of Pesticides, as on 31/03/2026".
* Each source PDF carries this disclaimer verbatim, which propagates to our
  derived data: *"The document has been compiled on the basis of available
  information for guidance and not for legal purposes."* Our label database is
  therefore **advisory grounding, not a legal label**. The physical product label
  always overrides it.

---

## 1. CIB&RC — Major Uses of Pesticides (registers)

| Field | Value |
| --- | --- |
| Publisher | Central Insecticides Board & Registration Committee (CIB&RC), Faridabad |
| Page URL | <https://ppqs.gov.in/divisions/cib-rc/major-uses-of-pesticides> |
| Edition | **as on 31/03/2026** (all six files) |
| Download date | **2026-08-25** |
| Landing dir | `data/raw/cibrc/` |
| Statutory basis | Registered under the Insecticides Act, 1968 |
| Role in pipeline | **Answer-side authority** — the only permitted origin of dose, dilution and pre-harvest interval values |

### 1.1 File inventory

`title_on_site` is the link text as it appears on the page above.
`original_filename` is the href target, preserved so the download is reproducible.
Local files were renamed for stable, sortable references.

| local filename | title_on_site | original_filename | pages | bytes | sha256 |
| --- | --- | --- | --- | --- | --- |
| `insecticides_20260331.pdf` | List of Major Uses of Pesticides (Insecticides) | `updated_mup_insecticide_as_on_31.03.2026_c.pdf` | 109 | 1,760,349 | `20fcd282d572e953815b56e8a2b83027da667ec844cf7bdfabb043daec315838` |
| `fungicides_20260331.pdf` | List of Major Uses of Pesticides (Fungicides) | `2._chemical_mup_fungicide_as_on_31.03.2026_0.pdf` | 83 | 1,413,647 | `2662c8f376bfa831743b105c1386185357b86230e0646f7a09bc00b652b5809f` |
| `bio_insecticides_20260331.pdf` | List of Major Uses of Pesticides (Bio-Insecticides) | `6._mup_bio_insecticide_31.03.2026.pdf` | 19 | 496,169 | `f9fe03458a57a0d1da39b9e901b018616faec5d3fe6bbfc0524d3bc83b3ed062` |
| `bio_fungicides_20260331.pdf` | List of Major Uses of Pesticides (Bio-Pesticides) Fungicide | `3._bio_pesticide_mup_biofungicide_as_on_31.03.2026.pdf` | 20 | 339,665 | `a993757ec05e80b0a9aca970d3772f4153efc934611950cd4105252f8c8f0156` |
| `herbicides_20260331.pdf` | List of Major Uses of Pesticides (Herbicides) | `4._herbicides_mup_as_on_31.03.2026.pdf` | 76 | 1,180,348 | `80d8c8ada76a90ab490f1d3a40cb65b2c0fa03f7c3cbc866d99d798e5345a478` |
| `pgr_20260331.pdf` | List of Major Uses of Pesticides (Plant Growth Regulators) | `5._pgr_mup_as_on_31.03.2026.pdf` | 13 | 578,297 | `ed0ca2988f896f4c4bd3cd931af1d713bda4b6a458999cac36e5c1785c7c5f19` |

Verify any file with:

```powershell
Get-FileHash data\raw\cibrc\insecticides_20260331.pdf -Algorithm SHA256
```

### 1.2 Document titles as printed on the PDF cover pages

The cover pages carry a different (longer) title than the site link text. Both are
recorded so either can be cited.

| local filename | cover-page title | internal sections |
| --- | --- | --- |
| `insecticides_20260331.pdf` | MAJOR USES OF PESTICIDES (Registered under the Insecticides Act, 1968) (UPTO–31.03.2026) — INSECTICIDES | 1. Agriculture use (p2) · 2. Insecticide combinations (p53) · 3. Public Health (p85) · 4. Household (p90) · 5. FAO locust control (p105) |
| `fungicides_20260331.pdf` | MAJOR USES OF PESTICIDES (Registered under the Insecticides Act, 1968) (UPTO - 31/03/2026) — FUNGICIDES | 1. Single product formulations (p2–41) · 2. Fungicide combinations (p42–79) |
| `bio_insecticides_20260331.pdf` | MAJOR USES OF PESTICIDES (Registered under the Insecticides Act, 1968) (As on – 31/03/2026) — BIO-INSECTICIDES | 1. Bio-insecticides (p2–15) · 2. Public health use (p15–18) |
| `bio_fungicides_20260331.pdf` | MAJOR USES OF BIO-PESTICIDES (Registered under the Insecticides Act, 1968) (Updated upto 31.03.2026) — BIO-PESTICIDES | 1. Bio-fungicides (p2–19) |
| `herbicides_20260331.pdf` | Major Uses of Pesticides (Registered under the Insecticides Act, 1968) (UPTO - 31/03/2026) — HERBICIDES | 1. Herbicide products (p2–41) · 2. Herbicide combinations (p42–67) |
| `pgr_20260331.pdf` | Major Uses of Pesticides (Registered under the Insecticides Act, 1968) (UPTO – 31/03/2026) — PLANT GROWTH REGULATORS (PGR) | PGR uses (p2–12) |

### 1.3 Scope decision

| local filename | status | reason |
| --- | --- | --- |
| `insecticides_20260331.pdf` | **PARSE** | pest control on scope crops |
| `fungicides_20260331.pdf` | **PARSE** | disease control on scope crops |
| `bio_insecticides_20260331.pdf` | **PARSE** | IPM / biological pest options |
| `bio_fungicides_20260331.pdf` | **PARSE** | IPM / biological disease options |
| `herbicides_20260331.pdf` | **ARCHIVE — do not parse** | weed control is out of advisory scope for V1 |
| `pgr_20260331.pdf` | **ARCHIVE — do not parse** | growth regulation is not plant protection |

Herbicides and PGR are retained on disk for provenance completeness and possible
later scope widening, but no pipeline stage reads them.

**Hard rule:** if a (crop, pest, active ingredient) triple is absent from the
parsed extract, no chemical option may be emitted for it. The advisory must fall
back to non-chemical measures plus `escalate_to_expert = true`. This rule is
mirrored in `src/system_prompt.txt`.

### 1.4 Text-layer triage (Phase 1)

All six PDFs carry a **real embedded text layer** — none is a scan, so no OCR is
required and no OCR-induced digit corruption can enter the pipeline. Verified two
independent ways: poppler `pdffonts` + `pdftotext -layout`, and PyMuPDF +
pdfplumber (`tools/phase1_triage.py`, raw output in
`data/interim/phase1_triage.json`).

| local filename | verdict | embedded fonts | chars on mid page | raster images | vector rects/page |
| --- | --- | --- | --- | --- | --- |
| `insecticides_20260331.pdf` | TEXT | TrueType, subset+embedded | 3,351 | 0 | 143–388 |
| `fungicides_20260331.pdf` | TEXT | TrueType, subset+embedded | 2,667 | 0 | 283–408 |
| `bio_insecticides_20260331.pdf` | TEXT | TrueType, subset+embedded | 2,707 | 0 | 163–364 |
| `bio_fungicides_20260331.pdf` | TEXT | TrueType, subset+embedded | 3,108 | 0 | 112–296 |
| `herbicides_20260331.pdf` | TEXT | TrueType, subset+embedded | 2,050 | 0 | 162–232 |
| `pgr_20260331.pdf` | TEXT | TrueType, subset+embedded | 2,723 | 0 | 169–401 |

Zero raster images on every sampled page rules out the scanned-page failure mode.
The high vector-rectangle count is the drawn table grid, which means ruled cell
borders exist for a lattice-flavour table parser to key on.

### 1.5 Prohibition list — banned / refused registration / restricted in use

**A separate document from the MUP registers above, and the only source of
prohibition data in this repo.** The MUP registers are a *registration*
register and carry no prohibition content whatsoever — verified in Phase 7
Step E by a regex sweep for `ban|prohibit|restrict|withdraw|refus|s.27A`
across all 231 parsed pages, which returned only false positives
("Bandicota" the rat genus, "Banana", "Bangalore"). Absence from label_db is
not evidence of a ban, and presence in it is not evidence of legality.

| Field | Value |
| --- | --- |
| Publisher | Directorate of Plant Protection, Quarantine & Storage (PPQS), Dept. of Agriculture & Farmers Welfare — same directorate as the MUP registers |
| Title | LIST OF PESTICIDES WHICH ARE BANNED, REFUSED REGISTRATION AND RESTRICTED IN USE |
| Edition | **Updated on 31.07.2026** (as printed on the document's own cover line) |
| URL | <https://ppqs.gov.in/sites/default/files/list_of_pesticides_which_are_banned_refused_registration_and_restricted_in_use.pdf> |
| Download date | **2026-09-01** |
| Local file | `data/raw/cibrc/banned_restricted_20230601.pdf` (6 pp, 129,383 bytes) |
| sha256 | `6bdd966bcbc1901503cfb0f91b740221016856a6923c5688602fdbbe29a3afe4` |
| Statutory basis | s.27A Insecticides Act 1968 notifications, RC decisions, and Supreme Court orders, cited per row |
| Role in pipeline | **The ban authority.** Sole input to `data/final/restricted_ai.csv`, which gates G4 in the verifier. |

Its three sections map exactly onto `restricted_ai.py`'s three tiers:

| section | content | rows | tier |
| --- | --- | --- | --- |
| I.A | banned for manufacture, import and use | 49 | `banned` |
| I.B | banned for use, manufacture for export continues | 5 | `banned` |
| I.C | withdrawn (reversible if data is submitted and accepted) | 8 | `banned` |
| II | refused registration | 18 | `refused_registration` |
| III | restricted in use, with per-entry conditions | 16 | `restricted_use` |

Built into `data/final/restricted_ai.csv` (98 rows — the 96 above plus two
corrected-spelling/alias duplicates) by
`tools/phase7_stepE_build_restricted_ai.py`, which machine-verifies every
transcribed name against the source PDF text before writing. See
`reports/phase7_stepE_restricted_ai.md`.

**The local filename retains the `20230601` stamp** from the URL slug it was
first located under; the document itself says 31.07.2026. Renaming it would
break the hash-to-filename record above, so the discrepancy is noted here
instead.

---

## 2. Kisan Call Centre (KCC) Query Dataset

| Field | Value |
| --- | --- |
| Purpose | Real farmer question phrasing, code-mixed language, intent distribution |
| Publisher | Department of Agriculture & Farmers Welfare, Govt. of India |
| Portal (original plan) | ~~`data.gov.in`~~ — dead end. Phase 7 Step A found data.gov.in's own KCC resource pages are unrenderable single-page apps with no working public API, and AIKosh's mirror listings returned "resource unavailable" (`reports/phase7_stepA_kcc_survey.md`). |
| Actual source used | HuggingFace dataset [`Omegaindebt/Kisan_Call_Centre_Transcripts`](https://huggingface.co/datasets/Omegaindebt/Kisan_Call_Centre_Transcripts) — a ~1,000,000-row mirror, 2009-03 to 2024-05, 37 states. No single-file hash: pulled via `datasets.load_dataset()`, not a static download. |
| Landing dir | `data/raw/kcc/` |
| Format | one dataset via `datasets.load_dataset()`, cached locally to `kcc_filtered.parquet` after filtering — not one file per state × year as originally planned |
| Filters applied (Phase 7 Step B) | `StateName` ∈ {Maharashtra, Karnataka, Telangana, Gujarat, Madhya Pradesh}; `QueryType` ∈ {Plant Protection, Disease Management}; `Crop` mapped to `src/scope.py::CROPS` via `crop_mapper.map_crop()`; `QueryText` ≥ 4 words; `KccAns` ≥ 15 chars. No year cutoff — an earlier `year>=2020` pass cut the pool ~73% and was removed after review. |
| Dedup (Phase 7 Step C) | crop-scoped 3-pass pipeline — exact hash, MinHash LSH, semantic embedding with a `pest_matcher`-based guard against merging different pests — plus a known-defect exclusion (mojibake text, crop/QueryText mismatches). `reports/phase7_stepC_kcc_dedup.md`. |
| Key columns | `StateName`, `DistrictName`, `Crop`, `crop_slug` (derived), `QueryType`, `QueryText`, `KccAns`, `CreatedOn`, `query_script`/`answer_script` (derived, Unicode block detection) |
| Licence | Government Open Data Licence – India (GODL-India). Full attribution statement and exclusions in `data/raw/kcc/SOURCES.md` (gitignored like the rest of `data/raw/` — regenerated by `tools/phase7_stepB_kcc_download_filter.py`) |
| Role in pipeline | **Question side** of the SFT pairs — never the source of chemical doses |

**Caveats:**
- Answers are free-text FTA call-centre notes — inconsistent, sometimes
  abbreviated, and roughly 30% in a regional script (Devanagari, Gujarati,
  Telugu, ...) rather than Latin/English. Treated as *intent signal only*;
  every agronomic recommendation must be re-grounded in the CIB&RC register,
  never trained on directly from `KccAns`.
- `crop_slug` (the structured `Crop` column) is trusted, but `QueryText`
  itself occasionally names a different crop than its own row's tag — a
  real KCC logging defect. Only 3 known instances are excluded so far; no
  general scanner for this class exists yet.
- ~7% of the pre-dedup pool had mojibake-corrupted `KccAns`/`QueryText`
  (upstream encoding loss, not introduced by this pipeline) — excluded
  systematically in Phase 7 Step C, not just the one instance first spotted
  by chance in a sample.

**Status:** acquired and deduped. 1,000,000 rows downloaded (2026-09-01) →
18,840 after Step B filtering → 5,692 after Step C dedup. See
`reports/phase7_stepB_kcc_download_filter.md` and
`reports/phase7_stepC_kcc_dedup.md`.

---

## 3. Supporting References (context only, not dose authority)

| Source | Use |
| --- | --- |
| ICAR / SAU (MPKV Rahuri, PDKV Akola, VNMKV Parbhani) package-of-practices | Regional ETLs, non-chemical/IPM sequencing, crop-stage context |
| ICAR-NCIPM pest advisories | Season/stage pest calendars for Maharashtra |
| State Dept. of Agriculture, Maharashtra advisories | District-level outbreak framing |

---

## Raw Drop Inventory

Append one row per acquisition. Never overwrite a row — add a new one.

| Date acquired | Source | File(s) in `data/raw/` | Rows / pages | SHA-256 (first 12) | Notes |
| --- | --- | --- | --- | --- | --- |
| 2026-08-25 | CIB&RC | `cibrc/insecticides_20260331.pdf` | 109 pp | `20fcd282d572` | Phase 0. Text layer OK. |
| 2026-08-25 | CIB&RC | `cibrc/fungicides_20260331.pdf` | 83 pp | `2662c8f376bf` | Phase 0. Text layer OK. |
| 2026-08-25 | CIB&RC | `cibrc/bio_insecticides_20260331.pdf` | 19 pp | `f9fe03458a57` | Phase 0. Text layer OK. |
| 2026-08-25 | CIB&RC | `cibrc/bio_fungicides_20260331.pdf` | 20 pp | `a993757ec05e` | Phase 0. Text layer OK. |
| 2026-08-25 | CIB&RC | `cibrc/herbicides_20260331.pdf` | 76 pp | `80d8c8ada76a` | Phase 0. Archived, not parsed. |
| 2026-08-25 | CIB&RC | `cibrc/pgr_20260331.pdf` | 13 pp | `ed0ca2988f89` | Phase 0. Archived, not parsed. |
| 2026-09-01 | PPQS prohibition list | `cibrc/banned_restricted_20230601.pdf` | 6 pp / 96 entries | `6bdd966bcbc1` | Phase 7 Step E. Closes CLAUDE.md Known Gap #1. Sole input to `data/final/restricted_ai.csv`. Doc says "Updated on 31.07.2026". |
| 2026-09-01 | HuggingFace `Omegaindebt/Kisan_Call_Centre_Transcripts` | `kcc/kcc_filtered.parquet` (derived — no single raw file, see §2) | 1,000,000 → 18,840 (Step B filter) → 5,692 (Step C dedup) | n/a (HF dataset pull, not a static file) | Phase 7. data.gov.in API dead (Step A survey); GODL-India attribution required, see §2. |

---

## Frozen artifacts

Frozen 2026-08-27 (Act 2, reviewed); `src/schema.py` re-frozen 2026-08-31
(comment correction) and again 2026-09-01 (two semantic additions — intended
as the LAST break before training-data generation). `src/system_prompt.txt`
and `src/schema.py` are byte-frozen. The prompt must be identical between Windows authoring and any
Linux training run; the schema decides which samples are allowed into
`data/final/`. A silent edit to either would invalidate every dataset built
after it.

**Supersedes an earlier freeze from the same date.** The first Act 2 pass froze
a pre-review draft in which dose was a single free-text `dose_per_acre: str`
with no cross-field validation. That draft was replaced before any training
data was generated; it was never used downstream. The draft files are kept for
reference at `archive/superseded_draft/` (see that folder's README) and are not
importable from the pipeline. The row below is the only frozen record for each
file — the draft's hashes have been removed, not appended alongside.

`.gitattributes` pins `src/schema.py -text` and `src/system_prompt.txt -text`
so git never rewrites their line endings. Both files are LF in index and
worktree (`git ls-files --eol`), UTF-8, no BOM. Hashes below are of the raw
bytes, taken with `.gitattributes` already in place.

| Date frozen | File | Bytes | SHA-256 |
| --- | --- | --- | --- |
| 2026-08-27 | `src/system_prompt.txt` | 3096 | `8b0a4b78c02a8c0286d3ee82acc7d47b73c4cb903a0c62b5f6fc1c1ca352b4a1` |
| **2026-09-01** | `src/schema.py` | 8656 | `8521721c7abe216984e627f0ed54d47f897ffdaf775fc03677828afb9244f810` |

### Re-freeze 2026-09-01 — `src/schema.py` (semantic; intended to be the LAST)

**This is the last freeze break before training-data generation.** Both prior
breaks were cheap only because no dataset, reward function or benchmark
existed. Once generation starts, `schema.py`'s own invalidation clause fires
and a further change costs all three. Everything known to be needed was
therefore batched here, and the survey behind it
(reports/phase6_stepA_verifier_design.md and the expressiveness sweep) went
looking for gaps rather than confirming the two already known.

Two additions. Both fix a case where the schema made a **correct answer
impossible**, not merely lossy — that was the bar, and it is why several other
real gaps below were left out.

#### 1. `ChemicalOption.phi_not_applicable: bool = False`

`phi_days=None` was carrying two distinct ground-truth states. label_db keeps
them apart across four columns: **16 rows** where the label positively states
no interval applies (seed dressers — `NR`, `Seed dresser`, `waiting not
required`) and **184** where it prints `-` / blank / `Nil` and the interval is
genuinely unknown. The old invariant forced `escalate_to_expert=True` on all
200. On the 16 that is an affirmatively **wrong** answer: the label says no
waiting period applies and the model was compelled to send the farmer to an
expert anyway.

It sits on `ChemicalOption`, not `Advisory`, because PHI is a property of the
product. **Six (crop, pest) pairs register both a seed dresser and a foliar
spray** — cotton/Jassid has `Imidacloprid 48% FS` (`NR`) beside
`Acephate 75% SP` (15 days) — so one advisory legitimately needs both states
at once. An advisory-level flag would have been a category error on those six.

New invariant: `phi_not_applicable=True` with a non-null `phi_days` is
**rejected**. Permitting both would recreate the overload the field removes.

#### 2. `Basis` gains `"unstated"`

Refuse-to-guess is enforced everywhere else in this codebase — `dose_parser`
returns `NEEDS_UNIT` rather than inventing a unit, `pest_matcher` returns
`unmatched` rather than picking a plausible pest — and the schema could not
express it. `dose` is required and a numeric basis demands `value_min`, so
"registered for your crop and pest, but I cannot state the dose" had exactly
one shape: `basis='free_text'` with no value, **structurally identical to the
10 rows whose dose genuinely is prose** (`1.0 g/plant & 22.2 to 25.6 Kg/ha`,
`Foliar spray`). **42 rows** have no parseable product dose (25 empty, 17
unparseable, of which 13 are the unit-unresolvable `NEEDS_UNIT` survivors).
The model's only alternatives were to invent a number or to drop a registered
chemical entirely.

New invariant: any option with `basis='unstated'` requires
`escalate_to_expert=True`. A chemical nobody can dose is exactly the case a
human should see.

#### Verifier changes made in the same commit

`verify.G6`'s `phi_not_applicable` carve-out was previously unreachable dead
code; it is now live and **verifies the model's claim in both directions** —
asserting no interval applies where CIB&RC does not say so fails the gate, and
so does leaving it unknown where CIB&RC does say so. New gate
`G9_unstated_dose_earned`: `unstated` is legitimate only where label_db has no
parseable dose; claiming it on a row that *has* one is a refusal to answer an
answerable question and fails.

A latent bug surfaced while wiring G6 and was fixed: `(crop, pest, a.i.)` is
not a unique key. **142 of 1104 triples match more than one label_db row, and
90 of those disagree on PHI** — `cotton / Aphid / {imidacloprid}` alone spans
six products with intervals of 7, 26, 40 and 50 days plus two where none
applies. The verifier took `rows[0]`, so a seed-dresser claim was being checked
against a foliar row. It now narrows by the model's `formulation` string
(design section 5, stage 3). Where the formulation does not disambiguate it
still falls back to the first row — the `AMBIGUOUS` verdict the design calls
for is **not yet implemented** and remains open.

#### Deliberate omissions

These are decisions, not oversights. Each was found by the sweep, each loses
precision, none makes a correct answer impossible — and every field is
something the model can get wrong and that then has to be verified.

| not added | rows affected | why not |
| --- | --- | --- |
| `spray_volume_not_applicable` | **70** (granular/dust/bait formulations, seed treatments, soil drenches) | The identical `None`-means-two-things overload as PHI. But label_db has **no spray-volume column at all**, so neither state is verifiable — the field would be an unverifiable claim. Unlike PHI it also forces no wrong answer; leaving both bounds `None` reads as "unknown" and nothing downstream acts on it. **Revisit if spray volume is ever extracted from the source PDFs.** |
| `nematode` / `mite` / `rodent` on `Cause.type` | **34** (Red spider mite 20, Root-knot nematode 12, rats 2) | Those 34 rows will train a nematode as `"pest"`. Imprecise, never false — and `Cause.type` is rated "weak consistency, never a WRONG" in the verifier design, so there is nothing to check it against. `nutrient` and `abiotic` remain unused by label_db. |
| `ChemicalOption` → `Cause` link | 335 of 740 cells name >1 pest | "Chemical A treats pests 1–2, B treats 3" has no structural home. In practice one chemical covers all pests named in a cell, and the linkage fits in `caution` prose. A `targets` field is large new verification surface for a rare case. |
| escalation reason | — | `escalate_to_expert` is a bare bool; `system_prompt.txt` lists four distinct triggers. The bool is expressible, the reason is not — but no correct answer becomes impossible. |
| a.i. dose on `ChemicalOption` | 475 numeric a.i. doses; **169 rows state a.i. and product dose on different bases** | `ChemicalOption` carries one `Dose` and it is the product dose, because a farmer measures product into a tank. Correctly out of scope. |

Also confirmed **not** gaps by the same sweep, and needing no change: range
doses are fully expressible (185 product ranges; `value_max=None` is
unambiguous — zero rows parse a range-looking cell without a max); multiple
options with different bases already work (21 pairs span >1 basis); and every
non-empty label_db basis already had a `schema.Basis` member.

#### Scope and verification of the edit

| | superseded | current |
| --- | --- | --- |
| SHA-256 | `13c6d7b0f2d051620614e010f638dd34497751d24a8f6d3187d9145fee180dec` | `8521721c7abe216984e627f0ed54d47f897ffdaf775fc03677828afb9244f810` |
| Bytes | 4837 | 8656 |
| Date | 2026-08-31 | 2026-09-01 |

The hash was recomputed **from the file on disk** before pinning, not copied
from a report. Doing so caught a real defect: the first write produced **187
CRLF line endings**, which would have hashed differently on a Linux training
run and defeated the `-text` attribute entirely. The file was normalised back
to LF (8843 → 8656 bytes) and re-hashed; `git ls-files --eol` now reports
`i/lf w/lf attr/-text` for both frozen files. `src/system_prompt.txt` was not
touched and still verifies against its original 2026-08-27 hash.

---

### Re-freeze 2026-08-31 — `src/schema.py`

**Reason: the per-acre comment was factually wrong.** The `per_acre` member of
`Basis` was annotated `# already converted from per_ha by label_db`. That
conversion had never happened: label_db stored `per_ha` exclusively, zero
`per_acre` rows, while the system prompt offers the model both bases. The
comment asserted a property of the data that did not hold, and a verifier
written against it would have compared a per-acre answer to a per-hectare
figure — a 2.47x error in the direction of overdose.

Rather than weaken the comment to match the data, the data was made to match
the comment: `src/dose_units.py` now derives four per-acre columns at build
time (`dose_ai_per_acre_{min,max}`, `dose_formulation_per_acre_{min,max}`),
populated only where basis is `per_ha` and NULL for every non-area basis. The
comment now reads `# derived from per_ha by label_db, area bases only`.

**Scope of the edit: one line, entirely inside a comment.** Verified before
re-freezing — `git diff` shows `1 file changed, 1 insertion(+), 1 deletion(-)`,
and the `Basis` members, all field names on `Advisory` / `ChemicalOption` /
`Dose` / `Cause`, and every validator are byte-for-byte unchanged. Size 4830 →
4837 bytes (+7, the length difference of the comment text).

**Why this was safe to do:** `schema.py`'s own docstring warns that a change
"once training-data generation starts... invalidates the dataset, the reward
function and the benchmark together." At the time of the edit none of those
existed — `data/` held only `raw/`, `interim/` and `final/`, with no generated
training data, no reward function and no benchmark. Nothing downstream needed
regenerating.

| | superseded | current |
| --- | --- | --- |
| SHA-256 | `53f68176d62820e4eb589bfaebc83ea2ee060ed84e0860716e014a9bf29af42f` | `13c6d7b0f2d051620614e010f638dd34497751d24a8f6d3187d9145fee180dec` |
| Bytes | 4830 | 4837 |
| Date | 2026-08-27 | 2026-08-31 |

`src/system_prompt.txt` was **not** touched and still verifies against its
original 2026-08-27 hash.

Pinned by `tests/test_schema.py` (14 tests over `Dose`, `ChemicalOption` and
`Advisory` invariants — basis-aware dose validation, PHI None-vs-zero,
out-of-scope/ununderstood-query guards, spray-volume ranges) and by
`tests/test_verify.py`, which covers the 2026-09-01 additions end to end:
the seed-dresser answer that used to be inexpressible, both directions of the
verified `phi_not_applicable` claim, `unstated` requiring escalation, and
`unstated` claimed on a row that does have a dose.

`src/freeze_check.py` hardcodes both hashes. `assert_frozen()` recomputes them
and raises `FrozenArtifactError` on any drift; every script that loads the
prompt calls it first.

Re-freezing is a deliberate act: replace the row above, update `FROZEN_SHA256`
in `src/freeze_check.py`, and record why — as was done here, three times. The
superseded hash is kept in `freeze_check.SUPERSEDED_SHA256` so an old checkout
is reported by name rather than as an anonymous mismatch. Recompute the hash
from the file on disk and confirm it before pinning it; pinning a value copied
from a report cannot detect a file that changed again in between.
