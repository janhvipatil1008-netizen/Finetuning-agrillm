# Phase 4 (PHI) Step A — waiting_period_phi surface survey

Source: the four in-scope raw CSVs in `data/interim/`, data rows only
(`assignment_kind` in {`ordinal_6`, `fallback_subset`}). Column:
`waiting_period_phi`. Read-only; no parser written.

## 1. Totals

- **Distinct strings: 228** (227 non-empty + the empty string)
- Cells: 2692

## 2. Surface patterns

`disposition` is a PROPOSAL for the parser step, not a fact about the data.

| pattern | distinct | cells | class | proposed disposition |
|---|---|---|---|---|
| `BARE_NUMBER` | 122 | 1604 | resolves | int (days) |
| `NULL_MARKER` | 6 | 527 | no-number | None |
| `BLANK` | 1 | 409 | no-number | None |
| `SEED_TREATMENT_PROSE` | 16 | 33 | no-number | None |
| `NUM_DAYS` | 16 | 26 | resolves | int (days) |
| `BARE_RANGE` | 8 | 17 | resolves | int (max of range) |
| `GROWTH_STAGE` | 9 | 10 | no-number | None |
| `NOT_REQUIRED_PROSE` | 6 | 10 | no-number | None |
| `PROSE_NO_NUMBER` | 7 | 9 | no-number | None |
| `DEFECT_COLUMN_COLLAPSE` | 7 | 8 | needs-decision | raise/quarantine |
| `NUM_WEEKS` | 5 | 8 | resolves | int (x7) |
| `UNCLASSIFIED` | 6 | 7 | needs-decision | DECISION |
| `RANGE_MONTHS` | 5 | 6 | resolves | int (max x30) |
| `NULL_MARKER_QUALIFIED` | 4 | 5 | no-number | None |
| `RESIDUE_CONDITION` | 2 | 4 | needs-decision | DECISION |
| `NUM_HOURS` | 2 | 3 | needs-decision | DECISION |
| `DEFECT_STANDARD_REF` | 2 | 2 | needs-decision | raise/quarantine |
| `DEFECT_DILUTION_TEXT` | 2 | 2 | needs-decision | raise/quarantine |
| `MIXED_UNITS` | 1 | 1 | needs-decision | raise/quarantine |
| `DEFECT_DOSE_TEXT` | 1 | 1 | needs-decision | raise/quarantine |

## 3. Examples, verbatim

### `BARE_NUMBER` — 122 distinct / 1604 cells

```text
'5'
    x111  committed parse_phi -> 5
'07'
    x108  committed parse_phi -> 7
'7'
    x106  committed parse_phi -> 7
'30'
    x104  committed parse_phi -> 30
'10'
    x99   committed parse_phi -> 10
```

### `NULL_MARKER` — 6 distinct / 527 cells

```text
'-'
    x473  committed parse_phi -> None
'NA'
    x24   committed parse_phi -> None
'Nil'
    x22   committed parse_phi -> None
'--'
    x5    committed parse_phi -> None
'NIL'
    x2    committed parse_phi -> None
```

### `BLANK` — 1 distinct / 409 cells

```text
''
    x409  committed parse_phi -> None
```

### `SEED_TREATMENT_PROSE` — 16 distinct / 33 cells

```text
'(wet slurry treatment)'
    x7    committed parse_phi -> None
'Seed dresser'
    x5    committed parse_phi -> None
'Seed treatment'
    x4    committed parse_phi -> None
'This is used as seed dresser'
    x2    committed parse_phi -> None
'Only one time seed treatment'
    x2    committed parse_phi -> None
```

### `NUM_DAYS` — 16 distinct / 26 cells

```text
'3 days'
    x4    committed parse_phi -> 3
'10days'
    x4    committed parse_phi -> 10
'26 days'
    x2    committed parse_phi -> 26
'05 days'
    x2    committed parse_phi -> 5
'5 days'
    x2    committed parse_phi -> 5
```

### `BARE_RANGE` — 8 distinct / 17 cells

```text
'7-10'
    x9    committed parse_phi -> 10
'3-5'
    x2    committed parse_phi -> 5
'35-89'
    x1    committed parse_phi -> 89
'1-3'
    x1    committed parse_phi -> 3
'8-10'
    x1    committed parse_phi -> 10
```

### `GROWTH_STAGE` — 9 distinct / 10 cells

```text
'Delayed dormant spray'
    x2    committed parse_phi -> None
'90 % Emergence of earhead'
    x1    committed parse_phi -> 90
'Single application by seed treatment before sowing.'
    x1    committed parse_phi -> None
'At the end of the Harvest'
    x1    committed parse_phi -> None
'3 applications after petal fall , 2 weeks later & after harvest'
    x1    committed parse_phi -> 21
```

### `NOT_REQUIRED_PROSE` — 6 distinct / 10 cells

```text
'Being seed treatment waiting not required'
    x5    committed parse_phi -> None
'Use as seed treatment, hence waiting period is not applicable.'
    x1    committed parse_phi -> None
'Not applicable for seed treatment'
    x1    committed parse_phi -> None
'waiting not required'
    x1    committed parse_phi -> None
'Use as a seed treatment, hence waiting period is not applicable'
    x1    committed parse_phi -> None
```

### `PROSE_NO_NUMBER` — 7 distinct / 9 cells

```text
'NR'
    x2    committed parse_phi -> None
'NA Seed dresse r'
    x2    committed parse_phi -> None
'required'
    x1    committed parse_phi -> None
'This is used as seed dresse r'
    x1    committed parse_phi -> None
'At the end of harvest'
    x1    committed parse_phi -> None
```

### `DEFECT_COLUMN_COLLAPSE` — 7 distinct / 8 cells

```text
'2 1'
    x2    committed parse_phi -> 2
'77 77'
    x1    committed parse_phi -> 77
'0 7'
    x1    committed parse_phi -> 7
'1 7'
    x1    committed parse_phi -> 7
'3 1'
    x1    committed parse_phi -> 3
```

### `NUM_WEEKS` — 5 distinct / 8 cells

```text
'Not less than7 weeks'
    x4    committed parse_phi -> 49
'Not less than 21 weeks'
    x1    committed parse_phi -> 147
'Not less than7 weeks'
    x1    committed parse_phi -> 49
'Not less than8 weeks'
    x1    committed parse_phi -> 56
'Not less than21 weeks'
    x1    committed parse_phi -> 147
```

### `UNCLASSIFIED` — 6 distinct / 7 cells

```text
'500 lit per ha'
    x2    committed parse_phi -> 500
'Aeration is waiting Period 07 days to be checked PH3 detector strips.'
    x1    committed parse_phi -> 7
'Aeration Period 24 hrs detector strips or 4 hosphine detect tubes should be used in the premises'
    x1    committed parse_phi -> RAISES
'February followed by 2 dusting in summer'
    x1    committed parse_phi -> 2
'Only one application before the buds swell, 3 pre harvest application'
    x1    committed parse_phi -> 3
```

### `RANGE_MONTHS` — 5 distinct / 6 cells

```text
'3½-4months Depending on the variety'
    x2    committed parse_phi -> 4
'3.5-4 months'
    x1    committed parse_phi -> 120
'3½-4months Depending on the variety'
    x1    committed parse_phi -> 4
'3-3½months Depending on the variety'
    x1    committed parse_phi -> 3
'3½-4months Depending on the variety'
    x1    committed parse_phi -> 4
```

### `NULL_MARKER_QUALIFIED` — 4 distinct / 5 cells

```text
'N.A (Seed Dresser)'
    x2    committed parse_phi -> None
'N.A(Seed Dresser)'
    x1    committed parse_phi -> None
'NA (Seed dresser)'
    x1    committed parse_phi -> None
'NA (Seed Dresser)'
    x1    committed parse_phi -> None
```

### `RESIDUE_CONDITION` — 2 distinct / 4 cells

```text
'As when residues not to exceed 25 ppm'
    x3    committed parse_phi -> 25
'There should be no residues on grains and straw of paddy14day s before the harvest'
    x1    committed parse_phi -> 14
```

### `NUM_HOURS` — 2 distinct / 3 cells

```text
'12 hrs'
    x2    committed parse_phi -> RAISES
'24 hours'
    x1    committed parse_phi -> RAISES
```

### `DEFECT_STANDARD_REF` — 2 distinct / 2 cells

```text
'IS:6313- 2001 (Part-2)'
    x1    committed parse_phi -> 6313
'IS:6313-2001 (Part-3)'
    x1    committed parse_phi -> 6313
```

### `DEFECT_DILUTION_TEXT` — 2 distinct / 2 cells

```text
'Dilution in water (lit/ha) As per requirement for uniform coating of seeds 500 lit per ha'
    x1    committed parse_phi -> 500
'Dilution in water- 500 liter/ha'
    x1    committed parse_phi -> 500
```

### `MIXED_UNITS` — 1 distinct / 1 cells

```text
'03 (day) or 48 (Hrs) Re- entry period after each application'
    x1    committed parse_phi -> RAISES
```

### `DEFECT_DOSE_TEXT` — 1 distinct / 1 cells

```text
'800 kg seed tubers of potato are dipped in the solutions of fungicide for 10 minutes. Tubers aft'
    x1    committed parse_phi -> 800
```

## 4. Blank vs explicitly absent

The frozen schema cannot tell these apart — see section 7.

| category | distinct | cells |
|---|---|---|
| blank cell (`''`) | 1 | 409 |
| `NULL_MARKER` | 6 | 527 |
| `NULL_MARKER_QUALIFIED` | 4 | 5 |
| `NOT_REQUIRED_PROSE` | 6 | 10 |
| `SEED_TREATMENT_PROSE` | 16 | 33 |
| `PROSE_NO_NUMBER` | 7 | 9 |
| `GROWTH_STAGE` | 9 | 10 |
| **explicitly-absent subtotal** | | **594** |
| **blank + explicit** | | **1003** of 2692 (37.3%) |

`NULL_MARKER` tokens seen: ['-', '--', '----', 'NA', 'NIL', 'Nil']

## 5. Ranges

**21 cells / 12 distinct strings** contain a numeric range.

**Rule (confirmed): a range collapses to the LARGER value.** Longer wait
= safer for the farmer, so this is the opposite of the dose rule (which
takes the lower bound) and the same safe direction. The committed
`parse_phi` already implements this via `max(nums)`.

- `BARE_RANGE` — 8 distinct: ['1-3', '14-21', '3-5', '35-89', '4-8', '5-6', '7-10', '8-10']
- `RANGE_MONTHS` — 5 distinct: ['3-3½months Depending on the variety', '3.5-4 months', '3½-4months Depending on the variety', '3½-4months Depending on the variety', '3½-4months Depending on the variety']
