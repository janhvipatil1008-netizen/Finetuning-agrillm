# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A fine-tuning dataset pipeline for a plant-protection advisory model covering
eight crops in Maharashtra, India (cotton, soybean, tur, gram, onion, tomato,
grape, pomegranate). It extracts legally-binding pesticide label claims — dose,
pre-harvest interval, registered crop×pest pairing — from CIB&RC "Major Uses of
Pesticides" PDFs into `data/final/label_db`, which is the answer-side authority
for training data, the reward function, and the benchmark.

Wrong output here is a farmer applying the wrong chemical at the wrong rate.
That is why the parsers refuse to guess (see "Design rules" below) — code that
looks over-cautious usually encodes a specific in-corpus failure documented in
`reports/`.

## Commands

Run everything from the `agri-llm/` directory (the git repo root).

```bash
python -m pytest tests/ -q                      # full suite, 600 tests, ~1s
python -m pytest tests/test_dose_parser.py -q   # one file
python -m pytest tests/test_pest_matcher.py::test_confidence_ladder -q   # one test
python -m pytest tests/ -q -k "crop_dependent"  # by name

python src/freeze_check.py        # verify the frozen schema/prompt hashes
python src/scope.py               # print crop/target counts
```

There is no pytest config file, no linter config, and no build step.
`tests/conftest.py` puts `src/` on `sys.path`, so tests import `schema`,
`pest_matcher` etc. as top-level modules — never as `src.schema`.

### Rebuilding data

```bash
python tools/run_phase3.py                          # data/raw/ -> data/interim/
python tools/build_label_db.py                      # data/interim/ -> data/final/label_db.{csv,parquet}
python tools/phase5_stepB_resolve_formulation.py    # patches label_db in place — MUST follow the build
python tools/phase6_stepB_build_pest_table.py       # -> data/final/pest_synonym_table.csv
python tools/phase7_stepE_build_restricted_ai.py    # -> data/final/restricted_ai.csv (needs the PPQS PDF)
```

`build_label_db.py` regenerates label_db from `data/interim/`, which **undoes
Phase 5**. Always run `phase5_stepB_resolve_formulation.py` straight after it,
or trainable rows drop from 627 to ~95.

`data/raw/` and `data/interim/` are gitignored — reproduce them per `SOURCES.md`,
which carries the PDF URLs, SHA-256s and edition dates. **`*.parquet` is also
gitignored**, so `label_db.parquet` is a local artifact: regenerate it with
`build_label_db.py` if it is missing.

## The freeze

`src/schema.py` and `src/system_prompt.txt` are frozen by SHA-256 in
`src/freeze_check.py`, with `-text` in `.gitattributes` so git cannot rewrite
their line endings between Windows authoring and a Linux training run.

**Do not edit either file.** If a change is genuinely required, it is a
deliberate re-freeze: update `FROZEN_SHA256`, the `SOURCES.md` → "Frozen
artifacts" section, and `tests/test_schema.py`. `schema.py`'s docstring warns
that a change after training-data generation starts invalidates the dataset,
the reward function and the benchmark together.

`src/scope.py` is **not** frozen and is edited as ground truth improves.

Re-frozen twice (2026-08-31 comment fix; **2026-09-01** adding
`ChemicalOption.phi_not_applicable` and `Basis` member `"unstated"`). The
2026-09-01 break is intended as the **last** one before training-data
generation — after that, schema.py's invalidation clause fires for real.
Always recompute the hash from disk before pinning: the 2026-09-01 write
produced CRLF endings that would have hashed differently on Linux.

## Architecture

### The pipeline is a chain of pure, separately-tested parsers

`tools/` scripts orchestrate; `src/` modules do the work and hold no I/O.
Each `src/` parser is pure, has a `__all__`, and is pinned by a test file
whose case count reflects how much the corpus fought back:

| module | job | tests |
|---|---|---|
| `crop_mapper.py` | crop cell → 0..n of the 8 slugs | 108 |
| `dose_parser.py` | dose cell → `ParseResult` (branch/pattern/Dose) | 93 |
| `parse_phi.py` | waiting-period cell → `Optional[int]` days | 57 |
| `formulation_resolver.py` | CIB&RC formulation code → `g` or `ml` | 54 |
| `pest_matcher.py` | (crop, pest name) → canonical organism | 182 |
| `dose_units.py` | per-hectare dose → derived per-acre | 23 |
| `verify.py` | advisory JSON → gates + graded score | 69 |
| `restricted_ai.py` | banned / refused / restricted a.i. lookup | (in test_verify) |
| `schema.py` | the model's output contract | 14 |

Every non-obvious branch in these traces to a numbered finding in `reports/`,
and the module docstrings cite them by filename. **Read the docstring before
changing a parser** — they are unusually long on purpose and explain which real
row would break.

### Two-sided data model

- **Answer side** — `data/final/label_db.{csv,parquet}`, 740 rows × 31 columns.
  Built by `tools/build_label_db.py`; rejected raw rows land in
  `data/final/exclusion_log.csv` (same 31 columns plus `exclusion_reason`)
  rather than vanishing.
- **Output side** — `src/schema.py`'s `Advisory` / `ChemicalOption` / `Dose`,
  the JSON the model must produce.

The verifier being built in Phase 6 joins these two. `src/pest_matcher.py` is
its pest-resolution stage; `reports/phase6_stepA_verifier_design.md` and
`reports/phase6_stepA_pest_survey.md` hold the agreed design.

### label_db column conventions

- **a.i. dose vs product dose is carried by column prefix**, not a discriminator
  column: `dose_ai_*` and `dose_formulation_*` each have the same six fields
  (`_branch`, `_pattern`, `_basis`, `_value_min`, `_value_max`, `_unit`, `_raw`).
  `dose_formulation_*` is the product dose — what goes in the tank — and is the
  verifiable one (688/740 numeric vs 475).
- `*_branch` ∈ `numeric` | `free_text` | `empty` | `unparseable`. A row is usable
  when both branches are `numeric` or `free_text` — the same predicate as
  `dose_parser.ParseResult.ok`. **627 of 740 rows qualify.**
- **PHI is four columns.** `phi_days` (nullable, `0` is a real value and never
  means unknown), `phi_outcome` (`resolved` | `not_applicable`), `phi_not_applicable`
  (True on only 16 rows, where the label *explicitly* says PHI does not apply —
  the other 184 `not_applicable` rows print `-`/blank/`Nil` and are genuinely
  unknown), and `phi_raw`.
- **Prefer the parquet over the CSV.** `phi_days` round-trips as nullable `Int64`
  in parquet but degrades to `float64` in CSV, silently reintroducing the
  0-vs-None collapse `parse_phi.py` exists to prevent.
- `dose_*_basis` has no `per_acre` member: CIB&RC prints every area dose per
  hectare (612 of 619 numeric product doses). Per-acre figures live in four
  **derived** columns — `dose_ai_per_acre_{min,max}` and
  `dose_formulation_per_acre_{min,max}` — computed by `src/dose_units.py`
  (1 ha = 2.4711 acres, rounded to 4dp), populated only where basis is
  `per_ha` and NULL for every non-area basis. They share `dose_*_unit`; the
  conversion is unit-preserving so there is no per-acre unit column.
- **Derived columns go stale.** Any script that changes a dose value must call
  `add_per_acre_columns(df)` before writing. `build_label_db.py` and
  `phase5_stepB_resolve_formulation.py` both do;
  `tests/test_dose_units.py` re-derives from the shipped file and fails if any
  row disagrees.

### Pest resolution is keyed on (crop, pest), never pest alone

Nine English pest names denote different organisms on different crops — most
sharply, `Fruit borer` is *Helicoverpa armigera* on tomato and *Deudorix
isocrates* on pomegranate, and the string alone cannot tell you which.
`match_pest(crop_slug, pest_string, synonym_table)` takes the table as an
argument and never loads one; build it once with `load_table()` and hold it,
since the constructor computes indexes. Use `match_all()` for raw label_db
cells — 335 of 729 name more than one pest.

## The verifier

`src/verify.py` is one implementation with three modes — `gate` (training
filter, passes only on `total == 1.0`), `score` (eval, partial credit),
`filter` (inference, gates only). Writing three would guarantee they drift.

**It loads `data/final/restricted_ai.csv` at import** and raises
`MissingBanListError` if that file is absent, empty, or malformed. That is
deliberate: an absent ban list must never read as "nothing is restricted".
The file now exists (Phase 7 Step E, 98 rows — see Known gaps), so import
succeeds normally; before that it did not, and G4 was non-functional. Point
`AGRI_RESTRICTED_AI` at a different list to override — `tests/test_verify.py`
does this in a fixture, and still pins the raising as contract.

Nine gates (any failure → `total 0.0`): JSON, schema, empty-when-not-answering,
restricted a.i., triple registered, unknown-PHI-escalates, trainable row,
dose basis, and `unstated`-dose-earned. Basis gates rather than grades because a correct number on the
wrong basis is worse than a wrong number. Six graded checks C1–C6, weighted in
`CHECK_WEIGHTS`; inapplicable checks leave the denominator rather than scoring
zero, so a model is never punished for a gap in label_db.

`expected_answerable()` is the single source of truth for the refusal slice —
generation, verification and benchmark construction all call it.

Shaky ground truth is an **exclusion, not leniency**: a defective row sets
`excluded=True` and drops the item rather than softening a check.

## Design rules the code already follows

- **Fail loudly or return None; never guess.** A dose cell with no resolvable
  unit comes back `unparseable`/`NEEDS_UNIT`. An unrecognised pest returns
  `unmatched`. A PHI cell holding an ISI standard reference raises
  `PHIParseError` for quarantine rather than returning its digits.
- **Distinguish "known bad" from "unknown".** `pest_matcher` returns
  `canonical_name=None` but a populated `matched_surface_form` and `notes` for
  a known-damaged label_db fragment — that must not score the same as a pest
  nobody has heard of. Same reason `exclusion_log.csv` keeps rejected rows.
- **Zero is not missing, and neither is "not applicable".** `phi_days=0` is a
  genuine same-day-harvest interval (Polyoxin D on grape); `phi_days=None` with
  `phi_not_applicable=True` is a label that positively states no interval
  applies (16 seed-dresser rows). Truthiness collapses all three.
- **Refusal has a shape.** `Dose.basis="unstated"` means "registered, but no
  dose can be stated" — distinct from `"free_text"` (the label's dose *is*
  prose). It forces escalation, and `G9` fails it on any row that does have a
  parseable dose.
- **Preserve the audit trail.** Every parsed value keeps its verbatim source
  cell (`*_raw`) and its provenance (`source_file`, `source_page`,
  `source_row_index`).

## Known gaps (do not silently paper over)

- ~~**No banned/withdrawn active-ingredient data exists anywhere in the repo.**~~
  **CLOSED (Phase 7 Step E).** `data/final/restricted_ai.csv` now exists — 98
  rows built from the PPQS consolidated list *"Pesticides which are Banned,
  Refused Registration and Restricted in Use"*, **31.07.2026 edition**
  (`data/raw/cibrc/banned_restricted_20230601.pdf`, sha256 `6bdd966bcbc1…`,
  logged in `SOURCES.md` §1.5). **G4 is functional and `verify.py` imports
  normally.** Rebuild with `tools/phase7_stepE_build_restricted_ai.py`, which
  machine-verifies every transcribed name against the source PDF and refuses
  to write an unverified list. See `reports/phase7_stepE_restricted_ai.md`.

  The premise that CIB&RC's registers carry prohibition data is **false and
  was checked**: a sweep of all 231 parsed MUP pages found zero prohibition
  content (only "Bandicota" the rat genus, "Banana", "Bangalore"). MUP is a
  registration register; prohibitions come from the separate PPQS list above.

  What actually collides with label_db is **3 rows, not the four molecules
  this gap used to name**:
  - **Monocrotophos** (1 row) and **Carbofuran** (2 rows) are on the list, as
    `restricted_use`.
  - **Carbosulfan and Benfuracarb are NOT on the PPQS list at all** — not
    banned, not refused, not restricted — though both are in label_db (2 and
    1 rows). The earlier claim that they are prohibited was unsupported.

- **Two open judgement calls inside the ban list** (both flagged in
  `restricted_ai.csv` `notes` and in the Step E report):
  - **Monocrotophos is encoded conservatively** as `restricted_use` with an
    empty `restricted_crops` (= every crop). The instruments are narrower:
    S.O. 1482(E) bans it on *vegetables* only, and S.O. 4294(E) cancels the
    *36% SL formulation* specifically. The conservative reading was chosen
    because 36% SL certificates have been void since 2024-10-03 and it is a
    WHO Class Ib pesticide — but it over-refuses. Reading the 2005 order
    literally would take its KCC Flag E hits from **37 to 0**, since every
    mention in that corpus is on a non-vegetable crop.
  - **Dimethoate** is scoped to `tomato;grape;pomegranate;onion` — the order
    names a *category* ("fruits and vegetables consumed as raw food items"),
    not a crop list, so the mapping to scope crops is this project's reading.

- **The ban list cannot express formulation-scoped carve-outs.**
  `restricted_ai.py`'s scope granularity is (a.i., crop) with no formulation
  dimension. So Carbofuran's exemption for *3% Encapsulated Granule* cannot
  be encoded — and label_db's two Carbofuran rows are `Carbofuran 03%CG`,
  precisely the exempted formulation, so both are refused as false positives.
  Same limitation affects Monocrotophos 36% SL, Captafol (foliar vs seed
  dresser) and Cypermethrin (3% smoke generator). Left over-refusing rather
  than over-approving, deliberately.

- **`restricted_ai.normalise_ai_name` empties any digit-initial name.** It
  splits at the first digit, so `'2,4,5-T'` → `''` and that entry is inert in
  the lookup. Out of scope for the 8 crops today, but a real hole.
- No spray-volume ground truth was extracted, though `ChemicalOption` carries
  `spray_volume_min/max_l_per_acre`.
- `scope.TARGETS` has two entries with no label_db rows (onion Basal rot, onion
  Anthracnose) and one mapped on an assumption flagged in the pest table's
  `notes` column (pomegranate Cercospora fruit spot).

## Conventions

- Phase-numbered work: `tools/phaseN_*.py` produces `reports/phaseN_*.md`.
  Survey first, report, get review, then build. Follow this when adding a phase.
- `reports/` is the project's memory. Prefer citing a report over re-deriving
  a finding.
- Commit messages: `phase N: <what changed>` with the load-bearing number in
  the subject (e.g. `phase 5: formulation unit resolver — 532/545 NEEDS_UNIT
  resolved, 627/740 trainable rows`).
- `archive/superseded_draft/` holds the pre-review schema draft; it is not live
  code and `freeze_check.py` does not look at it.
