# Phase 7 Step D — KCC quality tagging

Source: `tools/phase7_stepD_kcc_quality_tags.py`. Input
`data/interim/kcc_deduped.parquet` (5,692 rows, Step C). Output
`data/interim/kcc_tagged.parquet` — 34 columns: the 16 from Step C plus 18
flag columns. **Not committed**, per the brief.

## 0. Flag E could not be computed — and is NULL, not False

Flag E asks whether a row names a chemical on "the G4 ban list". **That list
does not exist.** `data/final/restricted_ai.csv` has never been sourced —
it is CLAUDE.md's first Known Gap, `restricted_ai.py` raises
`MissingBanListError` rather than let its absence read as "nothing is
banned", and `load_restricted_ai()` explicitly rejects an empty file for
the same reason ("An empty ban list reads as 'nothing is restricted',
which this module exists to prevent").

So `banned_chemical_query` is **`pd.NA` on all 5,692 rows**. Not `False`.
`False` would assert "this row names nothing banned" — a safety claim
nothing in this repo can currently support, and writing it would be the
same 0-vs-None collapse `phi_days` and `Dose.basis='unstated'` exist to
prevent.

What I did instead is the half that is real: **extract the chemicals**, which
is the ban-join's left side and is independently useful (§4). Once the
s.27A list is sourced, flag E is a one-column join away — no re-tagging.

Mechanically, `verify.py` is un-importable without a ban list, and flags C/F
need it. The import guard is cleared with a **sentinel placeholder** written
to a temp dir (never `data/final/`), holding one row whose
`active_ingredient` is `ZZSENTINELNOTAREALBANLIST` — a string no pesticide
is named, so even a mistaken `RESTRICTED_AI.check()` returns nothing rather
than a plausible wrong answer. The ban list is read by G4 and nothing else;
`normalise_ai`, `LabelDB` and `expected_answerable` never consult it, so
**flag F is exactly as correct as it would be with the real list present**,
and the placeholder cannot leak into a flag E answer because flag E is not
computed at all. The repo's guard stays armed for every other caller.

## 1. Per-flag counts

| Flag | Meaning | Rows | % |
|---|---|---|---|
| A | `answer_contains_advice` | 5,181 | **91.0%** |
| C | `pest_unmatchable` | 4,130 | **72.6%** |
| D | `crop_mismatch` | 67 | 1.2% |
| E | `banned_chemical_query` | — | **not computed (all NA)** |
| F | `label_db_matchable` | 1,410 | **24.8%** |
| G | `has_local_language_terms` | 47 | 0.8% |

Flag A trigger breakdown: `dose+verb` 3,153 · `chemical+dose+verb` 965 ·
`dose` 593 · none 511 · `verb` 293 · `chemical+dose` 155 · `chemical+verb`
19 · `chemical` 3.

Flag A by answer script — the detector includes Devanagari/Gujarati/Telugu/
Kannada unit and verb forms, so it is not blind to the ~30% of answers that
are not in Latin script:

```
answer_script   False   True
devanagari        105   1042
latin             304   3866
other             101    146
telugu              1    126
kannada             0      1
```

**91% of answers carry chemical advice.** This is the flag's whole point:
`KccAns` is a rich, tempting, and entirely ungrounded advice corpus. The
project already treats it as intent-signal-only; this quantifies why that
rule has to hold. One sample row recommends `TRIZOPHOS 30 ML` for tomato
leaf miner with no crop-registration basis at all.

## 2. Flag F per crop — the headline number

**How many queries per crop can produce a grounded, dose-stating SFT
example:**

| crop | rows | matchable | % | pest_unmatchable |
|---|---|---|---|---|
| cotton | 1,771 | **586** | 33.1% | 1,167 |
| tomato | 727 | **224** | 30.8% | 493 |
| soybean | 964 | **200** | 20.7% | 730 |
| gram | 720 | **143** | 19.9% | 562 |
| onion | 675 | **97** | 14.4% | 532 |
| tur | 404 | **78** | 19.3% | 315 |
| pomegranate | 352 | **56** | 15.9% | 279 |
| grape | 79 | **26** | **32.9%** | 52 |

**Grape falls to 26 matchable rows** — below the 30-row minimum-viable
threshold this project applied in Step C. Its *rate* is fine (32.9%, second
best); it simply started too small. Every other crop clears 30 comfortably.

The pool splits three ways by `expected_answerable()`:

```
1,410  ANSWERABLE               -> dose-stating SFT examples
  152  NO_REGISTERED_CHEMISTRY  -> escalation/refusal examples
4,130  PEST_UNKNOWN             -> clarifying-question examples (see §3)
```

Excluding the 67 crop-mismatched rows, the **dose-stating pool is 1,396
rows across 86 distinct (crop, pest) pairs**. Median matchable row has 8
label_db rows behind it (max 89, min 1). Densest pairs: cotton Whitefly
(103), cotton Thrips (89), onion Thrips (72), gram Wilt (65).

## 3. Flag C — the 4,130 unmatchable rows are mostly NOT a synonym-table gap

By reason:

```
3,465  no pest term found in query
  661  no match in synonym table
    4  ambiguous across crops
```

Only **665 rows named a pest-ish phrase at all**, across just **34 distinct
phrases**. The full list:

| rows | phrase | crops |
|---|---|---|
| 216 | `caterpillar` | cotton, gram, onion, pomegranate, soybean, tomato, tur |
| 129 | `blight` | all 8 |
| 61 | `stem borer` | cotton, gram, onion, pomegranate, soybean, tomato, tur |
| 50 | `borer` | cotton, gram, onion, pomegranate, soybean, tomato, tur |
| 35 | `grub` | cotton, gram, grape, pomegranate, tomato, tur |
| 24 | `worm` | cotton, gram, onion, soybean, tomato |
| 22 | `fly` | cotton, gram, onion, pomegranate, tur |
| 15 | `rot` | cotton, onion, pomegranate, soybean, tomato |
| 14 | `bug` | cotton, gram, grape, pomegranate, tomato |
| 13 | `spot` | cotton, onion, pomegranate, soybean, tomato |
| 12 | `black spot` | pomegranate, soybean, tomato |
| 12 | `leaf blight` | onion, tomato |
| 10 | `beetle` | cotton, gram, soybean, tomato |
| 8 | `nematode` | cotton, pomegranate, tomato |
| 5 | `fruit fly` | pomegranate, tomato |
| 4 | `bacterial blight` | soybean, tomato |
| 4 | `red mites` | gram, pomegranate |
| 4 | `red spot` | cotton, pomegranate |
| 3 | `red mite` | pomegranate, tur |
| 3 | `nematodes` | onion, soybean, tomato |
| 3 | `mildew` | cotton, gram, grape |
| 2 each | `root borer`, `hopper`, `leaf borer`, `pod caterpillar`, `red rot` | |
| 1 each | `leaf blotch`, `black caterpillar`, `bugs`, `downy blight`, `red bug`, `root wilt`, `stem caterpillar`, `weevil` | |

**Read this list carefully before "fixing" anything.** The top entries are
bare head nouns with no species-identifying modifier — `caterpillar`,
`blight`, `borer`, `grub`, `worm`, `bug`, `fly`, `rot`. These are **not
missing synonyms; they are underspecified questions.** "Caterpillar on
soybean" does not name an organism — it could be Semilooper, Tobacco
caterpillar, or Girdle beetle, each with different registered chemistry.
Mapping `caterpillar` → any canonical would be precisely the guessing
`pest_matcher` refuses to do ("It never guesses" — its own docstring).

That reframes 3,465 + ~600 rows from "unusable" to **the clarifying-question
training slice** — `Advisory.clarifying_question` and
`query_understood=False` exist in the frozen schema for exactly this, and
this is where the examples come from. It may be the most valuable thing this
tagging pass found: the largest single block of the corpus trains the
behaviour of *asking which pest* rather than guessing.

Genuine table-behaviour cases worth a look, all small and all arguably
correct as-is:
- `bacterial blight` on soybean/tomato (4 rows) — the only `ambiguous across
  crops` hits. `Bacterial blight` is a crop-dependent canonical
  (Xanthomonas spp. differ on cotton vs pomegranate), so pest_matcher's
  crop-independent fallback correctly refuses. It is not registered on
  soybean/tomato in label_db, so refusing is the right answer.
- `red mite`/`red mites` on gram/pomegranate/tur (7 rows) — `Red spider
  mite` exists for cotton only. Same crop-scoping behaviour, working.

## 4. Flag E — chemicals extracted (no ban verdict)

**71 distinct label_db molecules** named across query + answer text. Top 20:

```
161 mancozeb        121 emamectin benzoate   105 dimethoate     83 imidacloprid
 81 fipronil         79 carbendazim           61 cypermethrin   56 acephate
 47 thiamethoxam     43 profenofos            41 quinalphos     37 monocrotophos
 31 copper oxychlor  30 chlorpyriphos         26 indoxacarb     25 acetamiprid
 24 chlorantranilip  22 chlorpyrifos          21 metalaxyl      20 spinosad
```

**The refusal-training examples you were after are demonstrably there.**
`restricted_ai.py`'s docstring names Monocrotophos, Carbofuran, Carbosulfan
and Benfuracarb as chemicals whose status this project cannot settle from
CIB&RC alone. Three of the four appear in this corpus:

- **monocrotophos — 37 mentions**
- **carbofuran — 8 mentions**
- **carbosulfan — 3 mentions**

That is ~48 rows that would very likely become refusal examples the moment a
sourced ban list lands. I am **not** flagging them as banned here — that
verdict needs the s.27A instrument and date, not my recollection — but it
does mean flag E is worth unblocking, and the payoff is now quantified
rather than hypothetical.

## 5. Flag D — 67 crop mismatches (full list in the run log)

1.2% of rows, far below the ~10% the 2-of-20 sample in Step C suggested —
that estimate was small-sample noise. Distribution of (tagged → named in
text), top entries:

```
10  cotton -> soybean      9  soybean -> cotton     7  tomato -> soybean
 4  cotton -> onion        3  gram -> soybean       3  gram -> tur
 3  soybean -> gram        3  tur -> gram           2  onion -> cotton
```

Examples confirming these are real logging errors, not detector noise:

```
[cotton      vs soybean] "FARMER ASKED ABOUT SUCKING PEST CONTROL IN SOYBEAN CROP ?"
[onion       vs cotton ] "FARMER ASKED ABOUT ATTACK OF THRIPS , APHIDS , JASSIDS ON COTTON ?"
[pomegranate vs tomato ] "FARMER ASKED ABOUT CONTROL OF SUCKING PEST ON TOMATO ?"
```

**3 of the 67 are false positives** (95.5% precision), all from the same
root cause as the Moth-Bean defect in Step B — `crop_mapper`'s bare `gram`
token rule:

```
[tur vs gram] "Farmer asked about sucking pest problem in Pigeon gram"   <- 'pigeon gram' IS tur
[tur vs gram] "FARMER ASKED ABOUT ATTACK OF GRAM POD BORER IN PEA?"      <- 'gram pod borer' is a PEST name
[tur vs gram] "ATTACK OF GRAM POD BORER?"                                 <- same
```

That is now the third distinct instance of the bare-`gram` rule misfiring
(Moth Bean, and these two patterns). It is a small, well-characterised bug
with three known triggers — a `crop_mapper` hardening pass with pinned tests
would close all of them together.

## 6. Flag G — local-language coverage is much thinner than hoped

47 rows (0.8%). Terms: `arhar` 30, `mava` 9, `chana` 4, `dalimb` 3,
`kapas` 1.

Two caveats that shrink it further:
- **6 of 47 are boilerplate, not farmer language** — the KCC *Crop dropdown
  label* pasted into the query text ("Bengal Gram (Gram/Chick Pea/Kabuli/
  Chana) crop", "Cotton (Kapas) crop"). No multilingual signal there.
- **30 of the remaining 41 are just `arhar`** — the standard Hindi name for
  tur, ubiquitous in Indian English and arguably not code-mixing at all.

Strip both and **genuine code-mixed pest vocabulary is ~9 rows of `mava`**
(Marathi for aphid) plus a handful of `dalimb`/`chana`. Examples: *"Farmer
asked about Cotton crop mava control?"*, *"mava + karapa on soyabean"*.

**This undercuts the premise that KCC supplies local-language coverage.**
FTAs transcribe farmer calls into standardised English, so the farmer's own
vocabulary is largely normalised away before it reaches the log. If
multilingual robustness is a V1 goal, it will have to come from deliberate
paraphrase augmentation using `scope.SYNONYMS`, not from KCC as found.

One spelling gap spotted: `"mava + karapa on soyabean"` — `karpa`
(Anthracnose) is in `scope.SYNONYMS`, but spelled `karapa` here and missed.

## 7. 20-row sample

In the run log. Representative:

```
MAHARASHTRA cotton  "FARMER ASKED ABOUT ATTACK OF THRIPS , APHIDS , JASSIDS ON COTTON CROP ?"
  A[ADVICE:dose+verb] (Marathi) अॅक्टरा (थायोमिथोझोम 25%) 5 ग्रॉम/15 लिटर...
  C pest='Jassid' matched   D no   E NA   G none
  F matchable=True count=89 gradeable=89 -> ANSWERABLE

MAHARASHTRA gram    "asked about blight in gram"
  A[ADVICE:dose+verb] (Marathi) हरबरा मर - एम ४५ ३० ग्राम...
  C pest=None unmatchable ('blight', no match in synonym table)
  F matchable=False -> PEST_UNKNOWN      <- clarifying-question candidate
```

## Summary and open questions

The usable-pool arithmetic:

```
5,692  tagged rows
1,396  dose-stating SFT pool   (matchable, no crop mismatch, 86 crop×pest pairs)
  152  refusal/escalation pool (NO_REGISTERED_CHEMISTRY)
4,130  clarifying-question pool (PEST_UNKNOWN — mostly underspecified, not broken)
```

For review:

1. **Flag E is blocked on sourcing `restricted_ai.csv`.** ~48 rows naming
   monocrotophos/carbofuran/carbosulfan are waiting on it. Worth scheduling?
2. **Grape has 26 matchable rows**, under the 30 floor. Accept, augment, or
   drop grape from V1?
3. **Is the 4,130-row PEST_UNKNOWN block in scope as clarifying-question
   training data?** I read it as the most valuable finding here, but it
   changes the shape of the SFT set from what the roadmap assumed.
4. **`crop_mapper` bare-`gram` rule has three known triggers now.** Hardening
   pass with pinned tests?
5. **Local-language coverage is ~9 genuine rows.** If multilingual robustness
   is a V1 goal it needs a different source than KCC.

Stopping here per the brief.
