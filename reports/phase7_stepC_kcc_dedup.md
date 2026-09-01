# Phase 7 Step C — KCC dedup, Phase C v2 (threshold 0.97 + pest guard)

Source: `tools/phase7_stepC_kcc_dedup.py`. Phase A and B **unchanged**,
reloaded from their existing checkpoints per the brief. Phase C re-run with
two changes: threshold 0.92 → 0.97, and a pest-name guard using
`src/pest_matcher.py` that blocks a merge whenever two cluster members name
different canonical pests. Two known-defect exclusions (mojibake,
crop-mismatch) also now run between Phase B and Phase C — see §2, their
scope turned out larger than what v1's 20-row sample had shown. **Not
committed**, per the brief.

## 1. Full cascade

```
      18,840  raw (Phase 7 Step B output)
       8,329  after Phase A (exact, crop-scoped)
       7,116  after Phase B (MinHash LSH, crop-scoped)
       6,601  after known-defect exclusion (mojibake + crop-mismatch)
       5,692  after Phase C v2 (semantic, threshold=0.97, pest-guarded)  <- FINAL
```

Per-crop, final: cotton 1,771, soybean 964, tomato 727, gram 720, onion
675, tur 404, pomegranate 352, **grape 79**. All eight comfortably clear
the 30-row minimum.

Compare to v1's Phase C output (threshold 0.92, no guard): 4,122 total.
This run keeps **5,692** — 1,570 more real rows survive, even after
*also* removing 515 defective rows v1 didn't touch. The threshold change
did essentially all of that work (see §4).

## 2. Known-defect exclusion — scope was bigger than the 20-row sample suggested

The brief asked to exclude "the mojibake row" and "the 2 crop-mismatch
rows" — the specific instances spotted in v1's Phase D 20-row sample. A
systematic scan across the full 7,116-row Phase B pool (not just that one
random sample) found both were **undercounts of a real, larger class**:

- **Mojibake**: regex `\?{4,}` (4+ consecutive literal `?`, the signature
  of text that lost its encoding — e.g. `'??? ?? ???? ???? ??????? ?
  ????? / ??  ???? ??????????? ???? ?????? ?????'`) against `QueryText` OR
  `KccAns` matched **512 rows**, not 1. By crop: tur 146, gram 107, onion
  93, cotton 87, tomato 44, pomegranate 22, soybean 10, grape 3. This
  correlates with `answer_script` from Phase 7 Step B — 328 of the 512 are
  `answer_script='other'` (no real letters survive at all) and 164 are
  `answer_script='latin'` (numbers/units like "SC", "%", "ZC" survive
  around the corrupted words). The one row flagged in v1 is inside this
  512.
- **Crop-mismatch**: exact-text lookup for the two flagged strings found
  the *"How to control flower drop problem in soyabean crop?"* text
  recurs **three** times across the pool, tagged `gram`, `soybean`, and
  `tomato` respectively — only the `gram` and `tomato` copies are actually
  wrong (the `soybean`-tagged one is correct and was left alone). Plus the
  one `'...Bottleguard plant?'` row. **Net: 3 rows excluded, not 2** —
  matched by exact `(QueryText, crop_slug)` pair, not row position, so
  this stays reproducible if the pipeline re-runs.
- No overlap between the two sets. **515 total excluded.**

I expanded the exclusion to the full systematically-detected set rather
than only the specific rows named in the brief — leaving 491 more
mojibake rows and 1 more mismatched row in a set described as "ready for
label_db pairing" would have defeated the stated reason for excluding them
at all ("these are data defects, not training material"). Flagging the
scope correction explicitly rather than silently expanding it.

**Not done, and worth naming**: this was a targeted check (one regex, two
known text strings), not a general crop-mismatch scanner. 2 of the v1
20-row sample's 20 rows showed a QueryText/crop_slug mismatch — if that
~10% base rate holds pool-wide, there are likely more mismatched rows this
pass didn't catch, only the ones matching those two exact strings. A real
scanner (does QueryText name a crop word other than crop_slug's?) is still
worth building before label_db pairing, same recommendation as last report.

## 3. Per-crop breakdown of Phase C v2

```
crop         before -> after   raw clusters   split by guard
cotton        2,090 -> 1,771   175            1
soybean       1,136 ->   964    91            0
tur             433 ->   404    22            0
gram            809 ->   720    50            1
onion           830 ->   675    68            0
tomato          844 ->   727    76            1
grape            82 ->    79     3            0
pomegranate     377 ->   352    18            0
```

## 4. Largest cluster: 156 → 20

**Largest raw cosine cluster at threshold 0.97: 20** (down from 156 at
0.92). Raising the threshold alone did almost all of the work of fixing
the over-merging found in v1 — at 0.97 the embedding space no longer
lumps together every "FARMER ASKED ABOUT CONTROL OF X ATTACK ON COTTON
CROP" regardless of X. Only **3 of 505 raw multi-member clusters** needed
the pest guard to actually split them apart. That's a much smaller
intervention than expected going in — but the 3 it did catch are exactly
the failure mode it was built for:

```
crop=tomato  raw cluster size=5 -> split into 2 groups
  group (tag='Early blight', size=3):
    'Farmer needs information regarding control of Early Blight in Tomato crop ?'
    'Farmer need information regarding control measures of early blight of tomato crop?'
    'Farmer needs information regarding control measures of early blight control in Tomato crop?'
  group (tag='Late blight', size=2):
    'Farmer needs information regarding control measures of late blight in tomato crop?'
    'Farmer need information regarding control measures of late blight of tomato crop?'
```

**This one matters beyond just being a correct split**: `scope.py`'s own
`CONFUSABLE_PAIRS` lists `("tomato", "Early blight", "tomato", "Late
blight")` by name as a pair the model must be trained to discriminate,
specifically because a keyword-matching baseline would confuse them. At
threshold 0.97 without the guard, this cluster would still have merged
(same raw cluster, same 5 members) and collapsed exactly that pair into
one surviving example — silently removing the one thing this project's
own benchmark design says is worth testing. The other two catches:

```
crop=cotton  raw cluster size=2 -> split into 2 groups
  'Attack of Aphids and thrips on cotton?'                    (tag=Aphid)
  'Attack of Aphids,Thrips and Jassids  on cotton?'            (tag=Jassid)

crop=gram  raw cluster size=2 -> split into 2 groups
  'How to control SEMI LOOPER IN GRAM crop?'   (tag=Semilooper)
  'How to control WILT IN GRAM crop?'          (tag=Wilt)
```

## 5. 20-row spot check — holds

Re-sampled 20 rows from the new final set (same `random_state=0`, so a
different sample than v1 since the underlying pool changed). No mojibake,
no visible crop/QueryText mismatch, real chemical content throughout (e.g.
"Spray Imidaclopride 70 WP 7 gm/15 Liter of Water", "थायोमेथोक्साम ...
80 मिली प्रति एकड़"). Re-hash check: **0 exact duplicates remain.**

## 6. Output

`data/interim/kcc_deduped.parquet` — **5,692 rows**, overwritten.
`data/interim/kcc_dedup_phaseC_semantic.parquet` also updated (identical
content). Phase A/B checkpoints untouched.

**Not committed.** Waiting on review — in particular on the scope
correction in §2 (515 excluded vs. the 3 originally named) and whether the
still-undone general crop-mismatch scan should happen before this feeds
label_db pairing.
