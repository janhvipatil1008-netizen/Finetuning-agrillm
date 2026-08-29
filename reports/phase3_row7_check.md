# Row 7 Check — insecticides p27 r17 (quarantine-parent merge)

**Diagnosis only. No merge re-run, no CSV touched.** This corrects the record
on one of Step 2c's 49 merges: the quarantine-parent case (§4 of
`reports/phase3_step2c_merge.md`) put the fragment in the wrong place.
Confirmed by the user's manual PDF check; this report answers the five
questions and provides independent proof, using the table's own sibling row
as ground truth.

## 0. The table

`insecticides p27` carries the Aluminum-Phosphide fumigation sub-table,
7 real fields (Step 1b, Step 2b both documented this — see
`reports/phase3_step1b_rowgrid.md` §2.1): Name of Commodity / Common name of
the pest / Cond. / Weight of volume / Exposure period / Conc. in air (ppm) /
Aeration-Waiting. Rows 16 and 17 are both quarantined (`cols_unresolved`) —
too many fields for the 6-band crop-advisory schema every other page uses.

**Row 16 sits entirely on p27 — no page break, nothing wrapped.** Its 7
fields are fully intact and are the ground truth used below:

```
field[0] Stored whole cereals Millets Pulses
field[1] Rice weevil, Lesser grain Borer, Khapra Beetle, Rust red flour beetle, Pulse beetle, Dried fruit Beetle
field[2] Air tight cover
field[3] 300–400 gm/m3 (230–307 ml)
field[4] 48–72 Hr. for cover fumigation
field[5] 10 ppm
field[6] Partial aeration For at least 1hr. followed by24 hr. complete Aeration waiting period of 24 hr.
```

**Row 17 is the one that wraps to p28.** Its own field[1] (pest) and
field[6] (aeration) end mid-phrase in exactly the same two places row 16's
text continues — "...Khapra" and "...followed by" — which is what makes the
correct target unambiguous.

## 1. p27 r17's 7 field values BEFORE the merge

From `data/interim/phase3_step2c_manifest.json`, `parent.raw_before`
(the quarantine row's own extraction — this schema has no discrete columns,
only `raw_row_text`, `" || "`-joined in reading order):

```
field[0] Go down fumigation
field[1] Rice weevil, Lesser grain Borer, Khapra
field[2] Airtight cover
field[3] 150 gm/m3
field[4] 07days
field[5] 10 ppm
field[6] Partial aeration For at least 1 hr. followed by
```

7 fields, matching the table's own header exactly.

## 2. p28 r0's own column values (the fragment)

From the manifest's `fragment_row` (this row WAS classified through the
6-band crop-advisory system, `assignment_kind=fallback_subset`, because p28
is section-tagged `crop-advisory` — a mistag inherited from row-level section
tagging, not a Step 2c defect):

| column | value |
|---|---|
| crop | *(empty)* |
| pest_or_disease | `Beetle, Rust red flour beetle, Pulse beetle, Dried fruit Beetle` |
| dose_ai | *(empty)* |
| dose_formulation | *(empty)* |
| dilution_water | *(empty)* |
| waiting_period_phi | `24 hr. complete Aeration waiting period of 24 hr.` |
| method | *(empty)* |

Two own segments, landing in `pest_or_disease` and `waiting_period_phi` under
the (wrong-schema) 6-band assignment — but the segments themselves are real
row-local text, correctly extracted; only their column LABELS are meaningless
here since the table isn't 6-band.

## 3. What the merge script actually did, and why

`tools/phase3_step2c_merge.py`, the `quarantine_parent` branch
([lines 268–279](tools/phase3_step2c_merge.py#L268-L279)):

```python
if mode == "quarantine_parent":
    qk, qp, qr = QUAR_PARENT
    parent = next(q for q in quar_rows
                  if q["source_file"].startswith(qk)
                  and int(q["source_page"]) == qp
                  and int(q["source_row_index"]) == qr)
    before = parent["raw_row_text"]
    parent["raw_row_text"] = before + " " + frag["raw_row_text"]
```

It does a flat string concatenation: `parent.raw_row_text + " " +
frag.raw_row_text`, unconditionally. No field-index awareness, unlike the
`else` branch just below it ([line 288](tools/phase3_step2c_merge.py#L288),
`seg_to_column`) which appends each fragment segment to its own named column.
**Why:** the module docstring's justification (§ "Two special cases") was
that "a 7-field-schema row has no 6-band cells to append into" — true, but
the fix taken (concatenate the whole fragment onto the END) implicitly
assumed the row has exactly ONE wrapped cell, positioned last. That
assumption is wrong here: **two** cells wrap in this row — the pest field
(field 1 of 7) and the aeration field (field 6 of 7, the actual last field —
which the concatenation correctly targets for continuation, but only for the
*second* fragment segment, appended in the wrong place relative to the first).

## 4. Is the fragment in the correct column? — **No, plainly incorrect.**

Splitting the actual post-merge `raw_row_text` on `" || "` gives **8
segments for a table whose own header has 7**:

```
field[0] Go down fumigation
field[1] Rice weevil, Lesser grain Borer, Khapra
field[2] Airtight cover
field[3] 150 gm/m3
field[4] 07days
field[5] 10 ppm
field[6] Partial aeration For at least 1 hr. followed by Beetle, Rust red flour beetle, Pulse beetle, Dried fruit Beetle   <- WRONG: pest names appended to the aeration sentence
field[7] 24 hr. complete Aeration waiting period of 24 hr.                                                                 <- WRONG: spurious 8th field; this text is field 6's real continuation
```

Two faults, not one: (a) the pest-list fragment (`Beetle, Rust red flour
beetle, Pulse beetle, Dried fruit Beetle`) landed inside the aeration
sentence instead of completing the pest list, and (b) the aeration
fragment's own continuation got pushed out into a field position the table
does not have.

## 5. Not a display artifact — proven

This is a real column/field misplacement in the stored data, not merely how
`raw_row_text` prints. Two independent proofs:

**(a) Segment count.** `len(before.split(" || "))` = 7,
`len(after.split(" || "))` = **8** — verified directly against the actual
stored string (not reconstructed) in this diagnosis. A table with a fixed
7-field header cannot correctly have an 8-field row; the extra `" || "`
boundary is real, not cosmetic.

**(b) Cross-reference to row 16.** Row 16's field[1] and field[6] — the same
two fields, unwrapped because row 16 never crosses a page break — read
`...Khapra Beetle, Rust red flour beetle, Pulse beetle, Dried fruit Beetle`
and `...followed by24 hr. complete Aeration waiting period of 24 hr.`
respectively. That is exactly the join the merge should have produced for
row 17: fragment segment 1 → end of field[1] (pest), fragment segment 2 →
end of field[6] (aeration). Instead both fragment segments were appended
after field[6], in fragment order, with no attempt to route segment 1 back
to field[1].

## Correct merge (not applied — proposal only)

Reconstruct row 17 by field index rather than flat string append:

```
field[1] "Rice weevil, Lesser grain Borer, Khapra" + " " + "Beetle, Rust red flour beetle, Pulse beetle, Dried fruit Beetle"
       -> "Rice weevil, Lesser grain Borer, Khapra Beetle, Rust red flour beetle, Pulse beetle, Dried fruit Beetle"
field[6] "Partial aeration For at least 1 hr. followed by" + " " + "24 hr. complete Aeration waiting period of 24 hr."
       -> "Partial aeration For at least 1 hr. followed by 24 hr. complete Aeration waiting period of 24 hr."
```

Rejoin all 7 fields with `" || "` — result stays at 7 fields, and both
fragment segments land where row 16 shows they belong. This is specific to
this one row (the only quarantine-parent case in the 49-row merge set) — a
targeted correction, not a new general rule. Requires re-opening
`phase3_step2c_manifest.json`'s single `quarantine_parent` entry and
`quarantine.csv`'s p27 r17 row; does not touch any raw CSV, `src/schema.py`,
or any of the other 48 merges.

## Scope note

This is quarantine data — `reason_code=cols_unresolved`, never destined for
`label_db` or Phase 4 training data on its own. It does not block downstream
work. But the Step 2c manifest and report describe this merge as following
"the same rule" as the other 48 (append fragment to parent's raw text) without
flagging that this row's parent has a field structure the flat-append logic
was never built to respect — that description is now known wrong for this
one row and should not stand uncorrected in the audit trail.
