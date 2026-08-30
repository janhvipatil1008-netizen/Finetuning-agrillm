# Phase 4 (crop) Step A — CIB&RC crop string survey

Source: the four in-scope raw CSVs, data rows only (`assignment_kind` in
{`ordinal_6`, `fallback_subset`}). Column: `crop`, post forward-fill.

## 1. Totals

- **Distinct crop strings: 235** (234 non-empty + the empty string)
- Data-row cells: 2692
- Blank crop cells: 219

| bucket | strings | cells |
|---|---|---|
| in scope (maps to one of the 8 slugs) | 47 | 746 |
| out of scope | 187 | 1727 |
| blank | 1 | 219 |

## 2. scope.py has no crop aliases

The task said to check `scope.py`'s `SYNONYMS` dict for known aliases. It
has none for crops: every key and value in `SYNONYMS` is a PEST or DISEASE
name (`'gulabi bondhali' -> 'Pink bollworm'`, `'telya' -> 'Bacterial
blight'`). `scope.CROPS` is a bare list of 8 slugs with no variants. The
only crop-alias logic anywhere in the repo is the `SCOPE_MATCHERS` regex
block inside `tools/phase3_fallback_diagnosis.py`, a diagnostic script,
not a shared module. The mapping below is therefore new work, not a
lookup of something already recorded.

## 3. Proposed mapping, by slug

### `cotton` — 3 strings / 223 cells

| n | CIB&RC string | flags |
|---|---|---|
| 221 | `Cotton` | — |
| 1 | `Cotton (Soil drench)` | method qualifier |
| 1 | `Rice (Paddy) &cotton` | **MULTI-CROP** |

### `soybean` — 6 strings / 74 cells

| n | CIB&RC string | flags |
|---|---|---|
| 1 | `For rodent control in field, storage and crops like rice, soybean and coconut)` | **MULTI-CROP** |
| 1 | `Soya bean` | — |
| 1 | `Soyabean` | — |
| 69 | `Soybean` | — |
| 1 | `Soybean (Seed Treatment)` | method qualifier |
| 1 | `soybean` | — |

### `tur` — 15 strings / 44 cells

| n | CIB&RC string | flags |
|---|---|---|
| 2 | `Pigeon Pea` | — |
| 1 | `Pigeon Pea Helicoverpa armiger` | pest text bled in |
| 1 | `Pigeon Pea Heliothis sp.` | pest text bled in |
| 11 | `Pigeon pea` | — |
| 1 | `Pigeon pea (Tur/Arhar)` | — |
| 1 | `Pigeon pea Bollworm (Helicoverpa` | pest text bled in |
| 1 | `Pigeon pea or Red gram (Arhar/Tur)` | — |
| 7 | `Pigeonpea` | — |
| 1 | `Pigeonpea (Red Gram/Arhar /Tur)` | — |
| 4 | `Red Gram` | — |
| 1 | `Red Gram (Arhar/Tur)` | — |
| 1 | `Red Gram (Tur or Arhar)` | — |
| 10 | `Red gram` | — |
| 1 | `Red gram (Arhar/Tur)` | — |
| 1 | `Red gram (Tur or Arhar)` | — |

### `gram` — 6 strings / 52 cells

| n | CIB&RC string | flags |
|---|---|---|
| 1 | `Bengal Gram (Gram or Chickpea)` | — |
| 14 | `Bengal gram` | — |
| 5 | `Chick pea` | — |
| 22 | `Chickpea` | — |
| 9 | `Gram` | — |
| 1 | `Wheat, Gram` | **MULTI-CROP** |

### `onion` — 1 strings / 31 cells

| n | CIB&RC string | flags |
|---|---|---|
| 31 | `Onion` | — |

### `tomato` — 8 strings / 177 cells

| n | CIB&RC string | flags |
|---|---|---|
| 1 | `Cabbage/ Cauliflower, Tomato, Brinjal, Chillies, Beans, Ornamental` | **MULTI-CROP** |
| 2 | `T omato` | — |
| 169 | `Tomato` | — |
| 1 | `Tomato Foliar application` | method qualifier |
| 1 | `Tomato Soil drench` | method qualifier |
| 1 | `Tomato nursery` | method qualifier |
| 1 | `Tomato seedlings` | method qualifier |
| 1 | `Tomato/Chilli es` | **MULTI-CROP** |

### `grape` — 6 strings / 120 cells

| n | CIB&RC string | flags |
|---|---|---|
| 1 | `G rapes` | — |
| 49 | `Grape` | — |
| 67 | `Grapes` | — |
| 1 | `Grapes (Soil drench)` | method qualifier |
| 1 | `Grapes –` | — |
| 1 | `Grapes –Soil drench` | method qualifier |

### `pomegranate` — 2 strings / 25 cells

| n | CIB&RC string | flags |
|---|---|---|
| 24 | `Pomegranate` | — |
| 1 | `Pomegranate Alternaria fruit` | pest text bled in |

## 4. Out of scope

**187 distinct strings / 1727 cells** map to none
of the 8 slugs. Full list omitted per the task; the near-miss review is
section 5.

## 5. Near misses — deliberately excluded

Each of these contains a word that looks in-scope but names a DIFFERENT
crop. Getting any of them wrong would put the wrong label claim in front
of a farmer.

| n | string | why excluded |
|---|---|---|
| 4 | `Beans` | `French/Kidney/Cluster/Urd/Mung bean` — none is soybean |
| 1 | `Beans (Cowpea, moong, Urd)` | `French/Kidney/Cluster/Urd/Mung bean` — none is soybean |
| 1 | `Black Gram` | `Black gram`=urad, `Green gram`=moong, `Horse gram`=kulthi — all distinct from `gram` (chickpea/Bengal gram) |
| 11 | `Black gram` | `Black gram`=urad, `Green gram`=moong, `Horse gram`=kulthi — all distinct from `gram` (chickpea/Bengal gram) |
| 9 | `Blackgram` | `Black gram`=urad, `Green gram`=moong, `Horse gram`=kulthi — all distinct from `gram` (chickpea/Bengal gram) |
| 1 | `Citrus, Rubber, Paddy (Rice),Tea, Vegetables` | `French/Kidney/Cluster/Urd/Mung bean` — none is soybean |
| 1 | `Cluster Beans` | `French/Kidney/Cluster/Urd/Mung bean` — none is soybean |
| 4 | `Cow Pea` | `Cow pea`, `Green pea`, `Pea` — none is pigeon pea (=tur) |
| 1 | `Cowpea, Guar, Pea` | `Cow pea`, `Green pea`, `Pea` — none is pigeon pea (=tur) |
| 5 | `French bean` | `French/Kidney/Cluster/Urd/Mung bean` — none is soybean |
| 1 | `Green Pea` | `Cow pea`, `Green pea`, `Pea` — none is pigeon pea (=tur) |
| 3 | `Green gram` | `Black gram`=urad, `Green gram`=moong, `Horse gram`=kulthi — all distinct from `gram` (chickpea/Bengal gram) |
| 1 | `Green gram Whitefly` | `Black gram`=urad, `Green gram`=moong, `Horse gram`=kulthi — all distinct from `gram` (chickpea/Bengal gram) |
| 1 | `Green pea` | `Cow pea`, `Green pea`, `Pea` — none is pigeon pea (=tur) |
| 1 | `Greengram` | `Black gram`=urad, `Green gram`=moong, `Horse gram`=kulthi — all distinct from `gram` (chickpea/Bengal gram) |
| 1 | `Kidney bean` | `French/Kidney/Cluster/Urd/Mung bean` — none is soybean |
| 7 | `Pea` | `Cow pea`, `Green pea`, `Pea` — none is pigeon pea (=tur) |
| 1 | `Pea (Seed Treatment)` | `Cow pea`, `Green pea`, `Pea` — none is pigeon pea (=tur) |
| 1 | `Pulses (Black gram /Greengram)` | `Black gram`=urad, `Green gram`=moong, `Horse gram`=kulthi — all distinct from `gram` (chickpea/Bengal gram) |
| 1 | `Pulses (Cowpea, Mung bean, Urdbean)` | `French/Kidney/Cluster/Urd/Mung bean` — none is soybean |
| 2 | `Urd bean` | `French/Kidney/Cluster/Urd/Mung bean` — none is soybean |

