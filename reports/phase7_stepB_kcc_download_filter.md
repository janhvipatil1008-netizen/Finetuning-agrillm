# Phase 7 Step B — KCC download, exploration, and filter (v2)

Source: `tools/phase7_stepB_kcc_download_filter.py`. This supersedes the v1
run: two changes made after review — (1) the `year >= 2020` cutoff was
removed (all years 2009-2024 are kept), (2) `'Disease Management'` was
added alongside `'Plant Protection'` in the QueryType filter. `query_script`
/ `answer_script` columns were added, via Unicode block detection (not a
language model). Everything else unchanged: 5 states, 8 crops via
`crop_mapper` with the Moth Bean exclusion, text-length filters. Still no
deduplication, no pairing against label_db — stopping here per the brief.

## 1. Filter pipeline — row count at each step

```
   1,000,000  raw
     301,903  state in {Maharashtra, Karnataka, Telangana, Gujarat, Madhya Pradesh}
      64,499  QueryType in {'Plant Protection', 'Disease Management'}
      24,067  crop in our 8 slugs (crop_mapper, Moth Bean false positive excluded)
      18,933  QueryText >= 4 words
      18,840  KccAns >= 15 characters
```

Removing the year cutoff recovered the volume the v1 pass lost: 18,840 rows
vs. 6,512 before (2.9x). Adding `'Disease Management'` contributed only
+271 rows at the QueryType step (64,499 vs. 64,228) — it is genuinely a
small bucket, as expected; not a wasted addition, but not a major volume
driver either.

## 2. Per-crop counts, after all filters

| crop | rows |
|---|---|
| cotton | 7,457 |
| soybean | 3,176 |
| gram | 2,452 |
| onion | 2,351 |
| tomato | 1,719 |
| tur | 1,027 |
| pomegranate | 555 |
| grape | **103** |

Every crop grew 4-5x versus v1. Grape is still the thinnest by a wide
margin (103 rows) — consistent with it being the most Maharashtra-
concentrated of the 8 crops and least grown in the other 4 states — but
103 is a meaningfully different starting point than v1's 20 for deciding
whether it's usable.

## 3. Per-state counts, after all filters

| state | rows |
|---|---|
| Maharashtra | 7,162 |
| Madhya Pradesh | 5,675 |
| Gujarat | 3,956 |
| Telangana | 1,359 |
| Karnataka | 688 |

## 4. Script distribution

`query_script` (QueryText):

| script | rows |
|---|---|
| latin | 18,832 (99.96%) |
| other | 8 |

`answer_script` (KccAns):

| script | rows |
|---|---|
| latin | 13,254 (70.3%) |
| devanagari | 3,695 (19.6%) |
| other | 1,399 (7.4%) |
| telugu | 486 (2.6%) |
| kannada | 6 |

Cross-tab (query_script is latin for effectively all rows, so this is
mostly just the answer_script table again, but confirms there's no
systematic pairing of non-latin queries with non-latin answers or vice
versa — it's overwhelmingly "English question, answer in whatever script
the FTA typed in"):

```
answer_script  devanagari  kannada  latin  other  telugu
query_script
latin                3694        6  13252   1394     486
other                   1        0      2      5       0
```

**Confirms the finding flagged in v1**: farmers' questions are almost
universally transcribed in Latin script/English by the FTA, but nearly 30%
of answers are in a regional script — Devanagari (Hindi/Marathi, can't
distinguish at the script level) is the largest non-Latin share, then an
"other" bucket (Gujarati, Tamil, etc. — confirmed Gujarati by eye in the
v1 sample), then Telugu. This is now a quantified, filterable column rather
than an anecdotal observation — Step C can slice on `answer_script` however
it needs to (keep all, keep latin-only, route non-latin through
translation, etc.) without re-deriving this.

## 5. 10-row sample

```
MP, tomato, 2014: Q: "farmer want to know information about fungus attack
  of tomato ?"  A: "spray coper oxcy chloride @ 45 gram +streptrosycline @
  2 gram/pump."  [latin/latin]

Karnataka, gram, 2021: Q: "Asked about plant protection"
  A: "Suggested to spray KAVACH or CHLOROTHALONIL 0.5.g per lit. water"
  [latin/latin]

Gujarat, cotton, 2022: Q: "Ask about Angular leaf spot information in
  Cotton crop"
  A: (Gujarati script) "...STREPTOCYCLINE 1g + COPPER OXYCHLORIDE 20g/pump"
  [latin/other]

Karnataka, cotton, 2017: Q: "ASKING FOR PLANT PROTECTION"
  A: "RECOMMENDED:SPRAY MONOCROTOPHOS 2ML/LITRE"  [latin/latin]
```

Full 10-row output (with district, date, both script columns) is in the
run log; the above is representative.

**Worth flagging**: that last sample recommends Monocrotophos — one of the
active ingredients CLAUDE.md's "Known gaps" section already names as
present in label_db with **no banned/restricted-AI list yet in the repo**
to catch it. This is a live instance of exactly that gap, now confirmed in
the KCC pool too: raw `KccAns` text is a historical FTA answer, not a
verified one, and must never be used as a training target directly — the
project plan already accounts for this (KCC supplies the query, label_db
supplies the verified answer), but Step C's matching/pairing logic should
not accidentally lean on `KccAns` content as a signal of correctness for
anything, including which chemical to expect.

## 6. Output artifacts

- `data/raw/kcc/kcc_filtered.parquet` — **18,840 rows**, all original
  columns plus `crop_slug`, `query_script`, `answer_script`. Overwrites the
  v1 file.
- `data/raw/kcc/SOURCES.md` — updated row count (18,840) and caveats
  section (year-cutoff removal recorded, Disease Management addition
  recorded).

## Still open

- PII scan (done in v1: 4/6,512 rows, all institutional helpline numbers)
  has not been re-run against the larger 18,840-row pool — the phone-number
  regex should be re-applied before Step C, proportionally more raw text
  is now in scope.
- Regional-language `KccAns` handling (keep/translate/filter) — not
  decided, now with real per-script counts to decide against (§4).
- Whether the still-open "sample vs. full ~30M archive" question (v1 §1)
  matters less now that grape sits at 103 rows instead of 20 — your call
  whether that's enough, especially since Step C will likely lose further
  rows to dedup and label_db-crop×pest matching.

Stopping here per instructions. Waiting on review before Phase 7 Step C.
