# Phase 4 (PHI) Step C — phi_parse_report

Wrote C:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\interim\phi_parse_report.csv (3703 rows: every waiting_period_phi cell across the 4 in-scope files, all row kinds including headers)

## Coverage

| outcome | count | % |
|---|---|---|
| resolved | 1665 | 45.0% |
| not_applicable | 2012 | 54.3% |
| raised | 26 | 0.7% |

## Raised — full distinct list

26 raised cells, 22 distinct raw strings.

| raw_string | occurrences | files | error_detail |
|---|---|---|---|
| `As when  residues not  to exceed 25  ppm` | 3 | insecticides | PHI cell 'As when  residues not  to exceed 25  ppm' is a residue limit, not a waiting period — quara |
| `2 1` | 2 | insecticides | PHI cell '2 1' holds two or more unjoined numbers — adjacent columns merged during extraction. Quara |
| `500 lit per ha` | 2 | bio_fungicides | PHI cell '500 lit per ha' is a dilution volume, not a waiting period — quarantine, do not take its d |
| `Aeration is waiting  Period 07 days to  be checked PH3  detector strips.` | 1 | insecticides | PHI cell 'Aeration is waiting  Period 07 days to  be checked PH3  detector strips.' is a fumigant re |
| `Aeration Period 24  hrs detector strips or  4 hosphine detect  tubes should be used  in the premises to  signal safety of  atmosphere.` | 1 | insecticides | PHI cell 'Aeration Period 24  hrs detector strips or  4 hosphine detect  tubes should be used  in th |
| `IS:6313-       2001  (Part-2)` | 1 | insecticides | PHI cell 'IS:6313-       2001  (Part-2)' is an ISI standard reference, not a waiting period — quaran |
| `IS:6313-2001  (Part-3)` | 1 | insecticides | PHI cell 'IS:6313-2001  (Part-3)' is an ISI standard reference, not a waiting period — quarantine, d |
| `90 %  Emergence  of earhead` | 1 | insecticides | PHI cell '90 %  Emergence  of earhead' is a growth stage or application schedule, not a waiting peri |
| `77    77` | 1 | insecticides | PHI cell '77    77' holds two or more unjoined numbers — adjacent columns merged during extraction.  |
| `0 7` | 1 | insecticides | PHI cell '0 7' holds two or more unjoined numbers — adjacent columns merged during extraction. Quara |
| `1 7` | 1 | insecticides | PHI cell '1 7' holds two or more unjoined numbers — adjacent columns merged during extraction. Quara |
| `3 1` | 1 | insecticides | PHI cell '3 1' holds two or more unjoined numbers — adjacent columns merged during extraction. Quara |
| `4 5` | 1 | insecticides | PHI cell '4 5' holds two or more unjoined numbers — adjacent columns merged during extraction. Quara |
| `03 (day) or 48 (Hrs) Re-  entry period after each  application` | 1 | insecticides | PHI cell '03 (day) or 48 (Hrs) Re-  entry period after each  application' is a fumigant re-entry or  |
| `3  applications  after petal  fall , 2 weeks  later & after  harvest` | 1 | fungicides | PHI cell '3  applications  after petal  fall , 2 weeks  later & after  harvest' is a growth stage or |
| `February  followed by  2 dusting in  summer` | 1 | fungicides | PHI cell 'February  followed by  2 dusting in  summer' is a growth stage or application schedule, no |
| `Only one  application  before the  buds swell, 3  pre harvest  application` | 1 | fungicides | PHI cell 'Only one  application  before the  buds swell, 3  pre harvest  application' is a growth st |
| `800 kg seed  tubers of  potato are  dipped in the  solutions of  fungicide for  10 minutes.  Tubers after  treatment are  dried in shade  and then  sown.` | 1 | fungicides | PHI cell '800 kg seed  tubers of  potato are  dipped in the  solutions of  fungicide for  10 minutes |
| `1 0` | 1 | fungicides | PHI cell '1 0' holds two or more unjoined numbers — adjacent columns merged during extraction. Quara |
| `There should  be no  residues on  grains and  straw of  paddy14day  s before the  harvest` | 1 | fungicides | PHI cell 'There should  be no  residues on  grains and  straw of  paddy14day  s before the  harvest' |
| `Dilution in  water (lit/ha)  As per  requirement for  uniform coating  of seeds 500 lit  per ha` | 1 | bio_fungicides | PHI cell 'Dilution in  water (lit/ha)  As per  requirement for  uniform coating  of seeds 500 lit  p |
| `Dilution in  water- 500  liter/ha` | 1 | bio_fungicides | PHI cell 'Dilution in  water- 500  liter/ha' is a dilution volume, not a waiting period — quarantine |

## Sample (resolved + not_applicable, seed=20260415)

### resolved (8 of 1665)

```text
insecticides_20260331.pdf p65 row4
  raw:   '20'
  value: 20

insecticides_20260331.pdf p40 row15
  raw:   '7'
  value: 7

fungicides_20260331.pdf p2 row12
  raw:   '5'
  value: 5

insecticides_20260331.pdf p30 row21
  raw:   '5'
  value: 5

fungicides_20260331.pdf p56 row1
  raw:   '7'
  value: 7

insecticides_20260331.pdf p13 row13
  raw:   '03'
  value: 3

insecticides_20260331.pdf p73 row11
  raw:   '3'
  value: 3

fungicides_20260331.pdf p80 row8
  raw:   '28'
  value: 28

```

### not_applicable (7 of 2012)

```text
insecticides_20260331.pdf p106 row3
  raw:   ''
  value: 

fungicides_20260331.pdf p10 row14
  raw:   ''
  value: 

insecticides_20260331.pdf p73 row8
  raw:   ''
  value: 

insecticides_20260331.pdf p47 row12
  raw:   '-'
  value: 

fungicides_20260331.pdf p23 row0
  raw:   'NA'
  value: 

bio_fungicides_20260331.pdf p9 row5
  raw:   ''
  value: 

insecticides_20260331.pdf p107 row8
  raw:   ''
  value: 

```

## Regression check — the glued-unit fix cells

| raw_string | expected | actual | rows | ok? |
|---|---|---|---|---|
| `3½-4months  Depending on  the variety` | 120 | 120 | 1 | YES |
| `3½-4months  Depending  on  the  variety` | 120 | 120 | 2 | YES |
| `3½-4months  Depending  on the  variety` | 120 | 120 | 1 | YES |
| `3-3½months  Depending  on the variety` | 105 | 105 | 1 | YES |
| `3.5-4  months` | 120 | 120 | 1 | YES |

**All five regression cells correct: True**
