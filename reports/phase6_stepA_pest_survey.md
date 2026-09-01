# Phase 6, Step A — pest vocabulary survey

Survey only. No synonym table built. Produced by `tools/phase6_stepA_pest_survey.py`
over the 740 rows of `data/final/label_db.csv`, reconciled against `src/scope.py`.

---

## 1. Distinct `pest_or_disease` values

| measure | count |
|---|---|
| rows in label_db | 740 |
| rows with a non-null pest cell | 729 |
| **rows with an EMPTY pest cell** | **11** |
| distinct raw values | **481** |
| distinct after whitespace/OCR normalisation | 455 |

The 481→455 drop is pure PDF noise: doubled spaces, non-breaking spaces, and
words broken across a column boundary (`Stemphyliu m`, `Myrotheciu m`,
`oxyspor um`). 26 of the 481 "distinct" strings are the same text as another.

The 11 empty pest cells are rows the verifier can never use for a pest check —
they can still support a registration-existence claim on (crop, chemical), but
Stage 4 of the lookup has nothing to match against.

---

## 2. After splitting compound cells

Delimiters in this corpus: `,` `&` `;` `and` `/`, a full stop, a closing
parenthesis followed by new words, and — in three cells — a colon or dash
introducing the scientific name (`Fruit borer: Helicoverpa armigera Leaf miner:
Liriomyza trifolii`). Scientific names inside parentheses are masked before
splitting, so `Damping off (Pythium aphanidermatum, Rhizoctonia solani)` stays
one mention.

| mentions in cell | rows |
|---|---|
| 0 (empty cell) | 11 |
| 1 | 394 |
| 2 | 172 |
| 3 | 81 |
| 4 | 60 |
| 5 | 15 |
| 6 | 4 |
| 7 | 2 |
| 8 | 1 |

| measure | count |
|---|---|
| total pest mentions | **1342** |
| distinct mentions (common name + scientific name) | 363 |
| **distinct individual pest names (common name only, case-folded)** | **187** |
| distinct scientific names appearing in-cell | 84 |

**335 of 729 cells name more than one pest.** A verifier doing exact string
comparison against the cell would fail on 46% of the corpus.

### Coordination with a shared head noun

CIB&RC writes `Early & Late blight`, `Leaf & Fruit spot`, `Spotted & Spiny,
Pink American, Egyptian bollworm`. A naïve split emits `Early`, `Leaf`,
`Spotted` as pest names. The splitter borrows the head noun from the next
sibling that has one, so these expand to `Early blight` / `Late blight`, `Leaf
spot` / `Fruit spot`, and so on. Without this the mention count is inflated by
about 30 junk tokens.

---

## 3. Canonical groups

**73 canonical groups** cover all 187 surface forms and all 1342 mentions
(100%). No surface form is left unmapped, and no proposed group is empty.

| type | groups |
|---|---|
| pest (insect) | 29 |
| disease | 40 |
| mite | 1 |
| nematode | 1 |
| rodent | 2 |

The full group table with every surface form and scientific name is in §4
(per crop) — below are the groups where the clustering decision was not
mechanical and needs your sign-off.

### Groups that merge many surface forms

| canonical | type | scientific | surface forms merged |
|---|---|---|---|
| **Helicoverpa armigera** | pest | *Helicoverpa armigera* | `helicoverpa armigera`, `helicoverpa armiger`, `helicoverpa`, `heliothis armigera`, `heliothis sp`, `heliothis`, `armigera)`, `american bollworm`, `american boll worm`, `pod borer`, `pod borers`, `gram pod borer`, `chick pea pod borer`, `pod borer complex`, `tomato fruit borer`, `helicoverpa armigera maruca testulalis` |
| **Bollworm complex** | pest | *Helicoverpa* + *Earias* + *Pectinophora* | `bollworms`, `bollworm`, `boll worms`, `boll worm`, `bollworm complex`, `boll worm complex`, `boll worms complex`, `ball worm` |
| **Tobacco caterpillar** | pest | *Spodoptera litura* | `tobacco caterpillar`, `spodoptera litura`, `spodoptera`, `spodoptera spp`, `leaf eating caterpillar`, `tobacco leaf eating caterpillar`, `leaf worm` |
| **Jassid** | pest | *Amrasca biguttula biguttula* | `jassids`, `jassid`, `leaf hoppers`, `leaf hopper`, `leafhopper` |
| **Whitefly** | pest | *Bemisia tabaci* | `whitefly`, `whiteflies`, `white fly`, `white flies` |
| **Red spider mite** | mite | *Tetranychus urticae* | `mites`, `mite`, `red spider mite`, `red spider mites`, `two spotted spider mite` |
| **Semilooper** | pest | *Chrysodeixis acuta* | `semilooper`, `semi looper`, `semi-looper`, `green semilooper`, `green semi looper` |
| **Spotted bollworm** | pest | *Earias vitella* / *E. insulana* | `spotted bollworm`, `spotted boll worm`, `earias vitella`, `spiny bollworm`, `egyptian bollworm` |
| **Fusarium wilt** | disease | *Fusarium oxysporum* | `wilt`, `fusarium wilt`, `wilt of tomato`, `fungal wilt`, `seedling wilt` |
| **Seed and seedling rot** | disease | mixed | `seed rot`, `seedling rot`, `seedling rot disease`, `seed born disease`, `seedling disease`, `seedling blight`, `stem rot`, `seed`, `seedling`, `rot`, `other seedling`, `diseases` |

### Three deliberate splits — cases you might expect to be merged

1. **`Helicoverpa armigera` vs `Bollworm complex`.** On cotton, `Bollworms` is a
   *complex* of three species (the corpus says so outright: `Bollworms (American
   & Spotted bollworm)`, `Bollworms (Pectinophora gossypiella, Helicoverpa
   armigera, Earias vitelli)`). A model answering "pink bollworm" against a
   label row that says "Bollworms" is not exactly right and not exactly wrong.
   Kept as its own group so the verifier can decide the containment rule rather
   than have the merge decide it silently.

2. **`Leaf miner` vs `Tomato pinworm`.** See §7 — scope.py conflates these and
   label_db does not.

3. **`Bacterial blight (cotton)` vs `Bacterial blight (pomegranate)`.**
   *Xanthomonas citri* pv. *malvacearum* and *X. axonopodis* pv. *punicae*.
   Different pathogens, different chemistry, one English name.

### Scientific names as an independent key

84 distinct scientific names appear inside the cells, and they are a stronger
join key than the common names where present:

| scientific name | mentions |
|---|---|
| *Helicoverpa armigera* | 61 |
| *Spodoptera litura* | 17 |
| *Bemisia tabaci* | 16 |
| *Thrips tabaci* | 14 |
| *Meloidogyne incognita* | 9 |
| *Fusarium oxysporum* | 8 |
| *Liriomyza trifolii* | 6 |
| *Aphis gossypii* | 6 |

They carry their own OCR spread — `Helicoverpa amigera`, `Aphis gossipy`,
`Bemmissia tabaci`, `Pectinophora gossipiella`, `Thips tabaci`, `Chrysodexis
acuta`, `Amarasca bigutella` — so the synonym table has to normalise binomials
as well as common names.

---

## 4. Per-crop pest vocabulary

The number after each crop is canonical groups, not surface forms.

### cotton — 24 groups (222 rows, 68 surface forms)

| n | canonical | surface forms |
|---|---|---|
| 92 | Jassid | jassid, jassids, leaf hopper, leaf hoppers, leafhopper |
| 79 | Thrips | thrips |
| 78 | Whitefly | white flies, white fly, whiteflies, whitefly |
| 71 | Aphid | aphid, aphids, aphis |
| 57 | Bollworm complex | ball worm, boll worm, boll worm complex, boll worms, boll worms complex, bollworm, bollworm complex, bollworms |
| 26 | Helicoverpa armigera | american boll worm, american bollworm, helicoverpa armigera |
| 22 | Pink bollworm | pectinophora gossypiella, pink american, pink boll worm, pink bollworm |
| 17 | Spotted bollworm | earias vitella, egyptian bollworm, spiny bollworm, spotted boll worm, spotted bollworm |
| 12 | Tobacco caterpillar | leaf worm, spodoptera, spodoptera litura, tobacco caterpillar, tobacco leaf eating caterpillar |
| 9 | Grey mildew | grey mildew |
| 8 | Alternaria leaf spot | alternaria leaf, alternaria leaf blight, alternaria leaf spot |
| 7 | Mealybug | cotton mealy bug, mealy bug, mealy bugs |
| 6 | Sucking pest complex | aphids jassids white fly, sucking insects, sucking pest, thrips white fly, whitefly aphids |
| 6 | Leaf spot (unspecified) | leaf spot, leaf spots |
| 5 | Red spider mite | mite, mites |
| 4 | **Bacterial blight (cotton)** | angular leaf spot, angular leaf spot or black arm disease, bacterial bight, bacterial leaf blight |
| 4 | Root rot (Rhizoctonia) | root rot |
| 3 | Seed and seedling rot | seed born disease, seedling blight, seedling disease |
| 2 | Grey weevil | grey weevil |
| 2 | Fusarium wilt | fungal wilt |
| 1 each | Cutworm · Red cotton bug · Boll rot complex | cut worm · red cotton bug · boll rot complex |

### soybean — 35 groups (72 rows, 63 surface forms)

| n | canonical | surface forms |
|---|---|---|
| 21 | Tobacco caterpillar | leaf worm, spodoptera, spodoptera litura, spodoptera spp, tobacco caterpillar |
| 20 | Semilooper | green semi looper, green semilooper, semi looper, semi-looper, semilooper |
| 15 | Stem fly | shoot fly, stem fly |
| 13 | Girdle beetle | girdle beetle, gridle beetle |
| 8 | Seed and seedling rot | diseases, other seedling, rot, seed, seed rot, seedling, seedling rot, seedling rot disease |
| 7 | Whitefly | white fly, whiteflies, whitefly |
| 7 | Helicoverpa armigera | helicoverpa armigera, heliothis, pod borer |
| 7 | Anthracnose | anthracnose, pod blight |
| 6 | Leaf spot (unspecified) | leaf spot, leaf spots |
| 5 | Rust | rust |
| 4 each | Jassid · Fusarium root rot · Phytophthora root rot · Rhizoctonia seedling blight · Pythium seedling blight · Myrothecium leaf spot · Frog eye leaf spot · Alternaria leaf spot | — |
| 3 | Collar rot | collar rot |
| 2 each | Grey weevil (`leaf weevil`) · Root rot · Cercospora leaf spot · Dry root rot (`charcoal rot`) · Target leaf spot · Bihar hairy caterpillar · Leaf miner | — |
| 1 each | Root-knot nematode · Fruit borer · Red spider mite · Aphid · Defoliator complex · White grub · Termite · Cotyledonary spot · Stem blight | — |

### tur — 7 groups (44 rows, 15 surface forms)

| n | canonical | surface forms |
|---|---|---|
| 37 | Helicoverpa armigera | armigera), gram pod borer, helicoverpa armigera, helicoverpa armigera maruca testulalis, pod borer, pod borer complex |
| 8 | Pod fly | pod fly |
| 5 | Spotted pod borer | maruca vitrata, spotted pod borer |
| 4 | Root rot (Rhizoctonia) | root rot |
| 2 | Seed and seedling rot | seed rot, stem rot |
| 2 | Fusarium wilt | fusarium wilt, wilt |
| 1 | Jassid | leaf hopper |

Note tur's `leaf hopper` is glossed *Empoasca kerri* in-cell, not *Amrasca* —
a different species under the same English name (§7).

### gram — 13 groups (52 rows, 22 surface forms)

| n | canonical | surface forms |
|---|---|---|
| 39 | Helicoverpa armigera | chick pea pod borer, gram pod borer, helicoverpa armiger, helicoverpa armigera, heliothis armigera, heliothis sp, pod borer, pod borers |
| 5 | Fusarium wilt | seedling wilt, wilt |
| 4 | Root rot (Rhizoctonia) | root rot |
| 3 | House rat | indian house rat |
| 2 | Field rat | field rat |
| 2 | Seed and seedling rot | seed, seedling rot disease |
| 1 each | Tobacco caterpillar · Semilooper · Cutworm · Termite · Dry root rot · Collar rot · Damping off | — |

### onion — 8 groups (31 rows, 11 surface forms)

| n | canonical | surface forms |
|---|---|---|
| 18 | Purple blotch | purple blotch |
| 8 | Thrips | thrips |
| 6 | Downy mildew | downey mildew, downy mildew |
| 5 | Stemphylium blight | stemphylium, stemphylium blight, stemphylium leaf blight |
| 1 | White grub | root grub |
| 1 | Blight (unspecified) | blight |
| 1 | Damping off | damping-off |
| 1 | Post-harvest rot | post-harvest diseases |

Onion is the thinnest vocabulary in the corpus: 8 groups over 31 rows.

### tomato — 28 groups (175 rows, 53 surface forms)

| n | canonical | surface forms |
|---|---|---|
| 51 | Early blight | alternaria blight, early blight |
| 43 | **Fruit borer** | fruit borer, fruit borers |
| 39 | Late blight | late blight, light blight, tomato late blight |
| 25 | Whitefly | white flies, white fly, whiteflies, whitefly |
| 13 | Leaf miner | leaf miner, leaf minor |
| 13 | Thrips | thrips |
| 11 | Root-knot nematode | root knot nematode, root-knot nematodes |
| 9 | Red spider mite | mite, mites, red spider mite, red spider mites, two spotted spider mite |
| 9 | Tobacco caterpillar | leaf eating caterpillar, tobacco caterpillar |
| 9 | Aphid | aphid, aphids |
| 9 | Fusarium wilt | seedling wilt, wilt, wilt of tomato |
| 7 | Helicoverpa armigera | helicoverpa, helicoverpa armigera, pod borer, tomato fruit borer |
| 7 | Damping off | damping off, damping-off |
| 6 | Powdery mildew | powdery mildew |
| 5 | Jassid | jassids, leafhopper |
| 5 | Leaf spot (unspecified) | leaf spot |
| 5 | Septoria leaf spot | septoria leaf blight, septoria leaf spot |
| 3 each | Buckeye rot · Bacterial leaf spot · Ring rot | — |
| 2 | Fruit rot | fruit rot |
| 1 each | **Tomato pinworm** · Anthracnose · Grey leaf mould · Alternaria leaf spot · Fruit spot · Root rot · Bacterial wilt | — |

### grape — 11 groups (119 rows, 17 surface forms)

| n | canonical | surface forms |
|---|---|---|
| 61 | Downy mildew | downey mildew, downy mildew |
| 49 | Powdery mildew | powdery mildew |
| 28 | Anthracnose | anthracnose, anthracnose disease, anthraconase |
| 11 | Thrips | thrips |
| 6 | Mealybug | mealy bug, mealy bugs |
| 6 | Flea beetle | flea beetle |
| 5 | Red spider mite | mites, red spider mite |
| 1 each | Jassid · Rust · Bacterial leaf spot · **angular leaf spot (suspect, §7)** | — |

Grape is 87% three diseases. Downy + powdery + anthracnose = 138 of 158 mentions.

### pomegranate — 13 groups (25 rows, 20 surface forms)

| n | canonical | surface forms |
|---|---|---|
| 8 | Fruit spot | alternaria fruit spot, fruit spot, fruit spots, spot |
| 8 | Anthracnose | anthracnose, anthracnose disease |
| 5 | Thrips | thrips |
| 5 | Leaf spot (unspecified) | leaf, leaf spot |
| 4 | Fruit rot | fruit rot, phytophthora fruit rot |
| 3 | **Fruit borer** | fruit borer |
| 3 | Bacterial blight (pomegranate) | bacterial blight, bacterial blight alternaria |
| 3 | Cercospora leaf spot | cercospora leaf spot |
| 2 | Alternaria leaf spot | alternaria leaf spot |
| 1 each | **Pomegranate butterfly** · Whitefly · Aphid · Scale insect | — |

---

## 5. `scope.TARGETS` entries with no label_db ground truth

40 targets across 8 crops. **9 have no matching label_db row** even after
case- and space-insensitive comparison. They fall into two very different
buckets:

### Absent BY DESIGN — the `chem="none"` refusal cases (4)

| crop | target | why absent |
|---|---|---|
| soybean | Yellow mosaic | viral; no curative chemistry exists, so CIB&RC registers nothing against it |
| tur | Sterility mosaic | viral (mite-vectored); same |
| tomato | Leaf curl virus | viral; same |
| pomegranate | Wilt | `chem="none"` in scope.py |

These are exactly the cases scope.py's docstring says must not disappear. Their
absence from label_db is the *expected* signal, not a gap — the verifier should
treat them as `UNLISTED`, which is the correct verdict for "there is no
registered chemical", and the correct model behaviour is an empty
`chemical_options` plus non-chemical advice.

### Genuine gaps — targets we expected to cover with no ground truth (5)

| crop | target | chem | status |
|---|---|---|---|
| cotton | Bacterial blight | thin | **Present, under other names.** 4 rows: `Angular Leaf spot`, `angular leaf spot or black arm disease`, `Bacterial bight` (typo for blight), `Bacterial Leaf blight`. The canonical string `Bacterial blight` never appears verbatim on cotton. Fix in the synonym table, not a data gap. |
| onion | Basal rot | thin | **Real gap.** No onion row mentions basal rot or *Fusarium* on onion. |
| onion | Anthracnose | thin | **Real gap.** Anthracnose appears on grape, pomegranate, soybean and tomato — never onion. |
| tomato | Leaf miner (*Tuta absoluta*) | rich | **Mis-specified, not missing.** See §7. |
| pomegranate | Cercospora fruit spot | thin | **Ambiguous.** label_db has `cercospora leaf spot` (3) and `fruit spot` (4/8) on pomegranate but never the compound `Cercospora fruit spot`. Needs a call on whether these are one target. |

Two further targets matched only because of spacing — `Mealybug` (grape) vs
label_db `mealy bug`, and `Cutworm` (gram) vs `cut worm`. They are present;
the exact-match check simply fails on the space, which is itself an argument
for normalising whitespace before any lookup.

**Net: 2 hard gaps (onion Basal rot, onion Anthracnose), 1 naming fix (cotton
Bacterial blight), 2 decisions needed (tomato leaf miner, pomegranate
Cercospora fruit spot), 4 correct-by-design absences.**

---

## 6. `scope.SYNONYMS` reconciliation

19 entries, 12 distinct canonical values. Every one of the 12 canonical values
resolves to a real label_db surface form — **no entry maps to a non-existent
pest**. Two structural problems instead:

| entry | issue |
|---|---|
| `"helicoverpa" -> "Pod borer"` | **Backwards granularity.** In label_db, `Pod borer` is a surface form *of* *Helicoverpa armigera*, not the other way round, and `pod borer` never appears on cotton — where a farmer saying "helicoverpa" most likely means bollworm. Mapping the species name to a crop-specific common name loses information the table should preserve. |
| `"anar butterfly" -> "Fruit borer"` | Correct as farmer language, but on pomegranate the organism is *Deudorix isocrates*, which label_db also lists separately as `Pomegranate butterfly`. The mapping is right; the canonical target is under-specified (§7). |
| `"leafhopper" -> "Jassid"` | Correct and confirmed — `leafhopper` and `leaf hopper` both appear in label_db. |
| `"oily spot" -> "Bacterial blight"` | Correct for pomegranate. Silently wrong if applied to cotton, where `Bacterial blight` is a different pathogen. Needs crop scoping. |

17 of the 19 keys are farmer-facing aliases (13 Marathi/Hindi transliterations
plus `leafhopper`, `hopper burn`, `oily spot`, `anar butterfly`). Only
`pink bollworm` and `thrips` are identity mappings.

---

## 7. Ambiguous cases

### (a) One English name, different organisms on different crops

These are the reason the synonym table must be keyed by **(crop, surface_form)**
and not by surface form alone.

| surface form | crop A | crop B | evidence |
|---|---|---|---|
| **Fruit borer** | tomato = *Helicoverpa armigera* | pomegranate = *Deudorix isocrates* | 20 of 46 tomato mentions carry `(Helicoverpa armigera)` in-cell; **all 3 pomegranate mentions carry no scientific name at all**, and pomegranate separately lists `Pomegranate butterfly (Deudorix gossypi)`. The verifier cannot disambiguate pomegranate's from the string — only from the crop. |
| **Alternaria leaf spot** | cotton = *Alternaria macrospora* | tomato = *A. solani*, i.e. early blight | cotton has 8 such mentions in a run of leaf-spot rows; on tomato the same words appear alongside `Early blight (Alternaria solani)` |
| **Bacterial blight** | cotton = *Xanthomonas citri* pv. *malvacearum* | pomegranate = *X. axonopodis* pv. *punicae* | different chemistry, same English name |
| **Leaf hopper / Jassid** | cotton, tomato = *Amrasca biguttula biguttula* | tur = *Empoasca kerri* | tur row glosses `Leaf hopper (Empoasca kerri)` explicitly |
| **Whitefly** | cotton, tomato, soybean = *Bemisia tabaci* | pomegranate = *Siphoninus phillyreae* | pomegranate row glosses `Whitefly (Siphoninus phillyreae)` |
| **Aphid** | cotton, tomato = *Aphis gossypii* | pomegranate = *Aphis punicae* | pomegranate row glosses `Aphids (Aphis punicae)` |
| **Thrips** | onion, cotton, tomato = *Thrips tabaci* | grape, pomegranate = *Scirtothrips dorsalis* | plus one *Thrips palmi* on tomato |
| **Downy mildew** | grape = *Plasmopara viticola* | onion = *Peronospora destructor* | grape rows gloss the binomial; onion rows never do |
| **Anthracnose** | grape (28) = *Elsinoe ampelina* | soybean (7) = *Colletotrichum truncatum*, written as `pod blight` | pomegranate (8) = *Colletotrichum gloeosporioides* |
| **Wilt** | tomato = *Fusarium oxysporum* f.sp. *lycopersici* **or** *Ralstonia solanacearum* | gram, tur = *Fusarium* | tomato has 5 bare `wilt` mentions plus one explicit `Bacterial wilt (Ralstonia solanacearum)`. Bare `wilt` on tomato is genuinely undecidable. |

### (b) Pairs I am not certain about — need your call

1. **`Leaf miner` vs `Tomato pinworm`.** `scope.TARGETS["tomato"]` says
   `"Leaf miner (Tuta absoluta)"`. label_db disagrees: all 6 in-cell glosses on
   `leaf miner` say *Liriomyza trifolii*, and *Tuta absoluta* appears exactly
   once, called `tomato pinworm`, **listed in the same cell alongside leaf
   miner** (`Spinetoram 11.70% SC`) — which is CIB&RC stating they are
   different organisms. scope.py's canonical is a conflation of two species
   with different registered chemistry. Recommend splitting the target.

2. **`Dry root rot` vs `Charcoal rot`.** Both are *Macrophomina phaseolina*.
   Merged here (gram `dry root rot`, soybean `charcoal rot`). If your agronomy
   source treats them as distinct field diagnoses, unmerge.

3. **`Cercospora leaf spot` vs `Frog eye leaf spot`** on soybean. Frog eye is
   *Cercospora sojina*; the corpus's `Cercospora leaf spot` is glossed
   *C. kikuchii* (purple seed stain) in one cell but appears bare in others.
   Kept separate; low confidence.

4. **`Bollworms` (complex) vs the three named species.** Is a model answering
   `Pink bollworm` correct against a label row that says `Bollworms`? Kept as
   separate groups so the verifier decides. My recommendation: containment —
   a species answer is CORRECT against a complex row, but a complex answer is
   not correct against a species row.

5. **`Stem fly` vs `Shoot fly`** on soybean — merged on one occurrence.

6. **`Fruit spot` / `Leaf spot` / `Leaf & Fruit spot` on pomegranate.** Four
   surface forms, no scientific names, likely all *Alternaria alternata*
   (`Alternaria fruit spot` appears twice). Merged into `Fruit spot`; genuinely
   uncertain.

### (c) OCR artifacts and misspellings in the pest strings

Misspellings that are real and must be absorbed:

| in label_db | should be | n |
|---|---|---|
| `Downey mildew` | Downy mildew | 15 |
| `Bacterial bight` | Bacterial blight | 1 |
| `Anthraconase` | Anthracnose | 1 |
| `light blight` | Late blight | 1 |
| `Gridle Beetle` | Girdle beetle | 1 |
| `leaf minor` | Leaf miner | 1 |
| `Ball worm` | Bollworm | 1 |
| `Helicoverpa armiger` | *H. armigera* | 1 |
| `Helicoverpa amigera` | *H. armigera* | 2 |
| `Aphis gossipy` / `gossypi` / `gosypii` | *A. gossypii* | 6 |
| `Bemesia` / `Bemmissia tabaci` | *Bemisia tabaci* | 2 |
| `Pectinophora gossipiella` | *P. gossypiella* | 2 |
| `Thips tabaci` | *Thrips tabaci* | 1 |
| `Chrysodexis acuta` | *Chrysodeixis acuta* | 1 |
| `Amarasca bigutella` / `bigutulla` | *Amrasca biguttula* | 5 |
| `Alternaria porii` | *A. porri* | 1 |
| `Spilosoma 6rustak` | *Spilosoma obliqua* (digit is OCR noise) | 1 |

Column-break word splits, already handled in normalisation: `Stemphyliu m`,
`Myrotheciu m`, `oxyspor um`, `Plasmoparavitic ola`, `WhitefliesandRedspidermites`,
`Pectinophoragos sypiella`, `Helicoverpaarmig era`, `B acterial`.

**Truncated or bled cells — 49 surface forms / 59 mentions that are not pest
names at all:**

- Bare fragments: `diseases`, `seedling`, `rot`, `spot`, `seed`, `leaf`,
  `other seedling`, `armigera)`, `blight`, `stemphylium`
- Missing-delimiter runs: `whitefly aphids`, `aphids jassids white fly`,
  `thrips white fly`, `stem fly girdle beetle`, `stem fly girdle beetle whitefly`,
  `downy mildew anthracnose`, `bacterial blight alternaria`,
  `spodoptera spp. semilooper`, `pink american` (from
  `Spotted & Spiny, Pink American, Egyptian bollworm` — a comma is missing),
  `spodoptera litura helicoverpa armigera early blight leaf spot`
- Unbalanced paren: `mealy bugs (phenococcus solenopsis`
- Generic categories, not organisms: `sucking insects`, `sucking pest`,
  `defoliators`

Every one is mapped to a canonical group in the proposal above, but they should
be flagged `low_confidence` so the verifier can refuse to produce a `WRONG`
verdict against a row whose pest cell we already know is damaged — the same
treatment the Phase 6 verifier design gives `flag_pest_bled` rows.

**One suspect row:** grape `Angular leafspot, Downy mildew, Anthracnose`.
Angular leaf spot is not a recognised grape disease; it is cotton's. Combined
with the fact that the other two names in the cell *are* grape diseases, this
looks like a bled cell rather than a real claim. Worth checking against
`source_page` before the table treats it as grape ground truth.

---

## 8. Coverage gap against `scope.SYNONYMS`

| measure | count |
|---|---|
| distinct label_db surface forms | 187 |
| covered by a `SYNONYMS` key or value (whitespace/case-insensitive) | **17** |
| **uncovered** | **170 (91%)** |
| canonical groups (of 73) with any farmer-facing alias | **12** |
| **canonical groups with no alias at all** | **61** |

The 17 covered forms: `anthracnose`, `aphid`, `bacterial blight`,
`downy mildew`, `fruit borer`, `helicoverpa`, `jassid`, `leaf hopper`,
`leafhopper`, `pink boll worm`, `pink bollworm`, `pod borer`, `powdery mildew`,
`thrips`, `white fly`, `whitefly`, `wilt`.

This understates the gap in one direction and overstates it in another, and
both are worth being precise about:

- **Understates it.** `SYNONYMS` covers only the farmer→canonical direction.
  It has no entries at all for the *label_db→canonical* direction, which is
  what the verifier's Stage 4 actually needs. Every one of the 187 surface
  forms needs a mapping, including the 17 "covered" ones.
- **Overstates it.** Many of the 170 uncovered forms are orthographic variants
  the table absorbs cheaply (`whiteflies`/`white flies`, `semi looper`/
  `semilooper`). The expensive gap is the **61 canonical groups with no
  farmer-facing alias** — every disease of soybean, every seed-treatment target,
  the rodents, the nematode, and both spider mites. If the training data is
  generated from farmer-language queries, those 61 groups have no query
  vocabulary to generate from.

### Missing alias classes, by kind

| kind | examples with no `SYNONYMS` entry |
|---|---|
| Marathi/Hindi for diseases | Early blight, Late blight, Purple blotch, Rust, Damping off — soybean and onion have **no** local-language coverage at all |
| Scientific binomials | all 84 in-cell names; a model answering `Helicoverpa armigera` matches nothing today |
| Crop-specific common names | `Gram pod borer`, `Chick pea pod borer`, `Tomato fruit borer`, `American bollworm` |
| Whole organism classes | rodents (2 groups), nematode (1), mites (1), 40 disease groups minus the 4 with aliases |

---

## 9. What I need decided before building the table

1. **Key the table on `(crop, surface_form)`, not `surface_form`.** Nine
   English names resolve to different organisms depending on crop, and two of
   them — `Fruit borer` and `Bacterial blight` — carry different registered
   chemistry. A crop-agnostic table would silently license a pomegranate
   *Deudorix* answer against a tomato *Helicoverpa* row.

2. **Split `tomato / Leaf miner (Tuta absoluta)` into two targets.** label_db
   treats *Liriomyza trifolii* and *Tuta absoluta* as different pests and lists
   them in the same cell.

3. **Rule for complex-vs-species matching** (`Bollworms` vs `Pink bollworm`).
   My recommendation is containment, one-directional.

4. **Two real onion gaps** — Basal rot and Anthracnose have no ground truth.
   Either drop them from TARGETS or accept that the verifier returns `UNLISTED`
   for them.

5. **Whether the 49 fragment forms get `low_confidence`**, exempting them from
   `WRONG` verdicts the way `flag_pest_bled` rows are exempted.

6. **Scientific names are in scope for the table.** 84 of them, with their own
   misspellings. They are the highest-precision join key available and a model
   answering in binomials currently matches nothing.
