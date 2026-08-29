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

---

## 2. Kisan Call Centre (KCC) Query Dataset

| Field | Value |
| --- | --- |
| Purpose | Real farmer question phrasing, code-mixed language, intent distribution |
| Publisher | Ministry of Agriculture & Farmers Welfare, Govt. of India |
| Portal | `data.gov.in` — "Kisan Call Centre (KCC) — Farmers Call Query Data" |
| Landing dir | `data/raw/kcc/` |
| Format | CSV (one file per state × year slice) |
| Filters applied | `StateName == "MAHARASHTRA"`; crops restricted to `src/scope.py::CROPS` |
| Key columns | `StateName`, `DistrictName`, `Crop`, `QueryType`, `QueryText`, `KccAns`, `CreatedOn` |
| Licence | Government Open Data Licence – India (GODL) |
| Role in pipeline | **Question side** of the SFT pairs — never the source of chemical doses |

**Caveats:** answers are free-text call-centre notes — inconsistent, sometimes
abbreviated, occasionally naming products rather than active ingredients. Treated
as *intent signal only*; all agronomic recommendations must be re-grounded in the
CIB&RC register.

**Status:** not yet acquired.

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
| _pending_ | KCC | — | — | — | Step 2 |

---

## Frozen artifacts

Frozen 2026-08-27 (Act 2, reviewed). `src/system_prompt.txt` and `src/schema.py`
are byte-frozen. The prompt must be identical between Windows authoring and any
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
| 2026-08-27 | `src/schema.py` | 4830 | `53f68176d62820e4eb589bfaebc83ea2ee060ed84e0860716e014a9bf29af42f` |

Pinned by `tests/test_schema.py` (14 tests over `Dose`, `ChemicalOption` and
`Advisory` invariants — basis-aware dose validation, PHI None-vs-zero,
out-of-scope/ununderstood-query guards, spray-volume ranges).

`src/freeze_check.py` hardcodes both hashes. `assert_frozen()` recomputes them
and raises `FrozenArtifactError` on any drift; every script that loads the
prompt calls it first.

Re-freezing is a deliberate act: replace the row above, update `FROZEN_SHA256`
in `src/freeze_check.py`, and record why — as was done here.
