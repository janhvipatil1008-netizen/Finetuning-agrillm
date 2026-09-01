# Phase 7 Step E — building `data/final/restricted_ai.csv`

Source: `tools/phase7_stepE_build_restricted_ai.py`. Closes CLAUDE.md's
first Known Gap. `verify.py` now imports without `MissingBanListError`, G4
is functional, and Flag E on the KCC pool is answered. **Not committed**,
per the brief.

Full test suite: **617 passed** with the real list in place (including the
tests that pin `MissingBanListError` when the list is absent — those use an
env override and still hold).

## 1. The brief's step 1 premise was wrong — checked, not assumed

The brief said the CIB&RC PDFs already in `data/raw/cibrc/` include
banned/restricted information. **They do not.** A regex sweep for
`ban|prohibit|restrict|withdraw|refus|s.27A|27-A` across all 231 pages of the
four parsed registers returned only false positives:

```
"Bandicota bengalensis"   (a rat genus, in rodenticide crop cells)
"Banana", "Bangalore", "bangle"
```

Zero prohibition content. That confirms what `restricted_ai.py`'s docstring
and CLAUDE.md both already stated: MUP is a **registration** register, and
prohibitions are issued separately under s.27A. The list had to come from a
new source, exactly as CLAUDE.md said ("This needs a new sourced dataset,
not a derivation").

## 2. The source

Found the consolidated official list, published by **the same directorate**
(PPQS) that issues the MUP registers already in this repo:

| | |
|---|---|
| Title | LIST OF PESTICIDES WHICH ARE BANNED, REFUSED REGISTRATION AND RESTRICTED IN USE |
| Edition | **Updated on 31.07.2026** — one month old, not the 2023 revision the search result title advertised |
| URL | `https://ppqs.gov.in/sites/default/files/list_of_pesticides_which_are_banned_refused_registration_and_restricted_in_use.pdf` |
| Local | `data/raw/cibrc/banned_restricted_20230601.pdf`, 6 pp, 129,383 bytes |
| sha256 | `6bdd966bcbc1901503cfb0f91b740221016856a6923c5688602fdbbe29a3afe4` |

Logged in `SOURCES.md` §1.5 and the Raw Drop Inventory with the same
hash/date discipline as the CIB&RC drops, as `restricted_ai.py` requires.

Its three sections map onto `restricted_ai.py`'s three tiers exactly —
the module was clearly designed against this document.

## 3. What was built

**98 rows** in `data/final/restricted_ai.csv`. Loads cleanly through
`load_restricted_ai()`.

| tier | rows | | restriction_type | rows |
|---|---|---|---|---|
| `banned` | 63 | | `banned` | 55 |
| `refused_registration` | 18 | | `refused_registration` | 18 |
| `restricted_use` | 17 | | `restricted` | 17 |
| | | | `withdrawn` | 8 |

Section mapping: I.A banned (49) + I.B banned-for-use-export-continues (5) +
I.C withdrawn (8) → `banned`; II (18) → `refused_registration`; III (16) →
`restricted_use`; plus 2 spelling/alias duplicates (§5).

### Schema note — the brief's columns wouldn't have loaded

The brief specified `active_ingredient, restriction_type, effective_date,
notification_reference, notes`. `restricted_ai.py` **requires**
`active_ingredient, tier, restricted_crops, instrument, date, notes`, and
rejects any `tier` outside `{banned, refused_registration, restricted_use}`
— so `withdrawn` and `restricted` as tier values would have raised
`MissingBanListError`, and the missing `restricted_crops` column would have
too. The CSV therefore carries **both**: the loader's six required columns,
plus `restriction_type` (the brief's finer four-way label, including
`withdrawn`) and `source_section` for audit. Extra columns are ignored by
the loader.

## 4. Transcription is machine-checked

The PDF's numbered lists carry inline statutory citations and multi-line
restriction prose that no table parser recovers cleanly, so entries were
transcribed by hand. A typo here is a *safety defect* — a misspelled a.i.
produces a key that silently never matches, so a banned molecule would read
as unrestricted.

So the builder asserts every transcribed name occurs verbatim in the
extracted PDF text, and **refuses to write the file otherwise**. It caught
two real mismatches on the first run:

```
'2,4,5-T'                            -> PDF prints "2,4, 5-T" (stray space)
'Dichloro Diphenyl Trichloroethane'  -> PDF splits it across table columns
```

Both are now handled by explicit, documented probes rather than a silent skip.

## 5. Two source-document defects, carried both ways

The official PDF **misspells two molecules**:

| PDF prints | correct |
|---|---|
| `Endosulfron` (I.A #18) | **Endosulfan** |
| `Dicohlro Diphenyl Trichloroethane` (III #7) | Dichloro… (**DDT**) |

`normalise_ai_name` is a pure string reduction, so transcribing the typo
verbatim yields the key `'endosulfron'` — which can never match label_db's
`Endosulfan`. Endosulfan is Supreme-Court-banned; a lookup that misses it is
precisely the failure this file exists to prevent. Both are therefore
emitted **twice** — verbatim for audit against the source, and corrected so
the lookup fires — with the relationship recorded in `notes`.

**A third limitation, not fixable here:** `normalise_ai_name` splits at the
first digit, so any digit-initial name reduces to an empty key —
`'2,4,5-T'` → `''`. That entry is inert in the lookup. It's a banned
herbicide, out of scope for our 8 crops, so it doesn't bite now, but it is a
real hole in the normaliser worth knowing about.

## 6. Crop scoping — the condition logic the brief defers already exists

The brief says to treat `restricted` as `banned` "for now — we can add
condition logic later". **That logic is already implemented.**
`Restriction.applies_to()` returns `False` when a `restricted_use` row names
crops and the queried crop isn't among them; an empty `restricted_crops`
already means every crop.

Using it isn't a nicety — blanket-banning would be actively wrong:

- **Mancozeb** is banned only on Guava, Jowar, Tapioca — **none of our 8
  crops**. It is also the single most-mentioned chemical in the KCC pool
  (161 mentions). Blanket-banning it would refuse the most common
  legitimate fungicide advice in the corpus.
- **Quinalphos** — Jute, Cardamom, Sorghum. None of ours. 41 KCC mentions.
- **Chlorpyriphos** — Ber, Citrus, Tobacco. None of ours. 30 mentions.

So `restricted_crops` carries the crops each order actually names. Crops
outside `scope.CROPS` are still recorded verbatim (they simply never match a
slug — the correct behaviour). For restrictions scoped by **formulation** or
**operator** rather than crop, `restricted_crops` carries a non-crop scope
token (`public_health`, `stored_grain_fumigation`, `seed_treatment_only`)
which is never equal to a scope slug, so the row correctly never fires on
our crops while the real scope stays recorded.

Restrictions that **do** reach our 8 crops:

| a.i. | scope encoded | reaches |
|---|---|---|
| Malathion | `soybean;tomato;grape` | 3 scope crops, exactly as the order names |
| Dimethoate | `tomato;grape;pomegranate;onion` | **judgement call — see §8** |
| Monocrotophos | *(empty = all crops)* | **judgement call — see §8** |
| Carbofuran | *(empty = all crops)* | all 8 — formulation carve-out, see §7 |
| Trifluralin, Fenitrothion, DDT | *(empty = all crops)* | all 8; their carve-outs (wheat / locust / public health) are not scope crops |

## 7. Cross-check against label_db — 3 contradictions, and 2 are false positives

**3 of 740 label_db rows** name a molecule this list restricts. All 3 are
trainable; all 3 are `restricted_use` tier (no label_db row names an
outright-banned molecule).

```
[tomato ] Carbofuran 03%CG      pest=White fly              trainable=True
[soybean] Carbofuran 03%CG      pest=Root knot nematode     trainable=True
[cotton ] Monocrotophos 15%SG   pest=Aphids, Jassids, ...   trainable=True
```

**The two Carbofuran rows are false positives, and they expose a real
data-model limitation.** The order reads:

> "All formulations of Carbofuran **except Carbofuran three percent
> Encapsulated granule (CG)** along with the crop labels may be stopped
> from use"

Both label_db rows are `Carbofuran 03%CG` — *precisely the exempted
formulation*. But `restricted_ai.py`'s scope granularity is **(a.i., crop)**;
it has no formulation dimension, so "3% CG is fine, everything else is not"
cannot be expressed in the CSV contract. The same limitation affects
Monocrotophos (36% SL specifically), Captafol (foliar vs seed dresser) and
Cypermethrin (3% smoke generator).

I left the conservative encoding — it over-refuses rather than
over-approves, which is the correct direction for a safety check — but this
is a schema gap worth an explicit decision. Options: add a
`restricted_formulations` column, or accept 2 lost trainable rows.

Contradiction detail written to
`data/interim/label_db_ban_contradictions.csv`.

### CLAUDE.md's Known Gap text is partly inaccurate

It names four molecules as prohibited-but-present-in-label_db. Checking each
against the authoritative list:

| molecule | on the official list? | in label_db |
|---|---|---|
| Monocrotophos | **yes** (restricted) | 1 row |
| Carbofuran | **yes** (restricted) | 2 rows |
| **Carbosulfan** | **NO** | 2 rows |
| **Benfuracarb** | **NO** | 1 row |

Carbosulfan and Benfuracarb appear **nowhere** in the 31.07.2026
consolidated list — not banned, not refused, not restricted. On this
evidence they are legal, and CLAUDE.md's claim about them is unsupported. I
have not edited CLAUDE.md; flagging for your call. (Caveat: absence from
*this* document isn't proof no other instrument touches them, but this is
the consolidated official list.)

## 8. Flag E re-run — 99 rows, but the number is highly sensitive

The Step D tagger now detects the real list automatically (falling back to
the sentinel, with Flag E as `NA`, if it's ever absent — it never
silently reports "nothing is banned"). Re-run on all 5,692 rows:

```
E  banned_chemical_query : 99 (1.7%)   [list: 98 restrictions]
```

| restriction hit | rows |
|---|---|
| Dimethoate `[restricted_use]` | 54 |
| Monocrotophos `[restricted_use]` | 37 |
| Carbofuran `[restricted_use]` | 8 |

By crop: tomato 25, cotton 18, onion 17, soybean 16, pomegranate 11, tur 6,
grape 4, gram 2. **Zero rows name an outright-`banned`-tier molecule** — no
KCC query or answer mentions Alachlor, Endosulfan, Phorate, etc.

**91 of the 99 hits flow directly from the two judgement calls in §6**, so
this is not a robust number. Sensitivity:

| decision | encoding | hits |
|---|---|---|
| **Monocrotophos** | empty = all crops *(current, conservative)* | **37** |
| | strictly the 2005 vegetables order → `tomato;onion` | **0** |
| **Dimethoate** | `tomato;grape;pomegranate;onion` *(current)* | **54** |
| | `tomato;onion` | 41 |
| | `tomato;grape` | 28 |

Monocrotophos is the sharp one: **all 37 mentions are on non-vegetable crops
(cotton, tur)**, so reading the 2005 order strictly would drop it to zero. I
chose the conservative encoding because S.O. 4294(E) cancelled the dominant
36% SL formulation outright (certificates void since 2024-10-03) and it is a
WHO Class Ib highly hazardous pesticide — but the order's *literal* crop
scope is vegetables only. Your call.

Depending on those two decisions, Flag E is somewhere between **~36 and 99
rows**.

## 9. Open questions

1. **Monocrotophos scope** — conservative all-crops (37 hits) or literal
   2005 vegetables-only (0 hits)?
2. **Dimethoate "consumed as raw food items"** — which of the 8 crops does
   that category cover? I read it as tomato/grape/pomegranate/onion (54
   hits); tomato+grape alone gives 28.
3. **Formulation-scoped restrictions** (§7) — extend the CSV with a
   `restricted_formulations` column, or accept that Carbofuran 3% CG (2
   trainable label_db rows) is wrongly refused?
4. **CLAUDE.md Known Gap text** — Carbosulfan and Benfuracarb are not on the
   official list. Correct that text?
5. **`normalise_ai_name` empties any digit-initial name** (`2,4,5-T` → `''`).
   Worth fixing in `restricted_ai.py`?

Stopping here per the brief. Nothing committed.
