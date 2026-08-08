---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ce803d1a7d67173eacef4dea3aade42bc0bf6dde0156cc6956319a1978f65126'
step_id: 'S04'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Settle whether the 2023 and 2024-early Modelo 303 designs are layout-identical

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_303/`

## Description

- Enumerate the five bundled Modelo 303 designs the open-ended revision spans, keyed on the design FILE so the two 2024 halves are distinct subjects.
- Measure every adjacent pair on four signals: box-number offset movement, per-sheet total positions, slot occupancy in both directions, and box-set membership.
- Compare the result against the occupancy signal's claim and against the sub-year decision record's claim.

## Outcome

**The occupancy signal is right and the decision record's conclusion is wrong.** The 2023 and early-2024 designs are **not** layout-identical.

Four real fields are retired into reserved space between them, all on sheet DP30302, all in the Regimen Simplificado block: the employee-count and maximum-employee-count slots for Actividad 1 at offsets 1110 and 1116, and the same pair for Actividad 2 at offsets 1236 and 1242. Each reads as a live Regimen Simplificado field in the 2023 design and as `Reservado para la AEAT` in the early-2024 design. The gate's failure text names the first three of the four; the fourth at offset 1242 is beyond its three-item sample.

Both documents measured honestly and neither measured the same thing. The decision record ran a box-number-keyed pass and a per-sheet total-positions pass, and this Step reproduces both exactly: zero of 174 shared boxes moved, zero boxes added or removed, and every sheet total unchanged. Those two signals are **structurally incapable** of seeing a slot retired into reserved space, because the reserved block absorbs the freed bytes exactly, so no offset shifts and no page grows. The record's error is not a measurement error, it is inferring layout identity from two signals that cannot observe the class of change that occurred. The gate's own module prose states this property; the record did not run the third pass.

The consequence changes the split's shape without changing its size. The open-ended revision spans **five** distinct design epochs, not the four the record concluded: 2023, early 2024, late 2024, 2025, and 2026 onward. The revision count stays five, because the period-token partition still splits 2024 and the year-edge constraint is unchanged, but the pairing changes: where the record concluded five revisions covering four epochs with exactly one layout-identical pair, the measurement gives five revisions covering five epochs with **no duplicate layout at all**. Every revision must parse its own design.

The full adjacent-pair inventory, keyed on the design file:

- **2023 to 2024-early.** 0 of 174 shared boxes moved, 0 added, 0 removed, sheet totals identical, **4 slots retired into reserved space**, 0 revived, 0 box numbers re-described.
- **2024-early to 2024-late.** 0 of 174 shared boxes moved, **8 boxes added** (108, 111, 165 through 170), 0 removed, sheet totals identical, 0 retired, **3 slots revived from reserved to real**, 2 box numbers re-described.
- **2024-late to 2025.** 0 of 182 shared boxes moved, 0 added, 0 removed, sheet DP30302 grows from 1706 to 1900 positions, **1 slot retired** at offset 1425 and **1 revived** at offset 1535, which is the same Regimen Simplificado surface module relocating rather than disappearing.
- **2025 to 2026.** **127 of 182 shared boxes moved**, 1 box added (112), 0 removed, sheet DP30305 grows from 1523 to 1528, 0 retired, **1 revived** at offset 441 carrying the rectificativa importe for box 111, 1 box number re-described.

A second finding falls out and it invalidates a rationale recorded in the gate itself. The gate declines to assert the **reserved-to-real** direction on the stated ground that it "measures zero across the whole bundled corpus, so an assertion for it would ship vacuous". Keyed on the design file rather than on the parsed year, that direction has **five positive cases in Modelo 303 alone**: three at the mid-2024 boundary, one at 2024-late to 2025, and one at 2025 to 2026. **Corrected by a later measurement:** the recorded rationale is not an artefact of the one-design-per-year inventory, as this record first concluded. Measured across every exporting revision's claimed span under the inventory exactly as it ships, the reverse direction has 32 transitions in four modelos against 16 retirements, so the rationale was never true of the corpus it describes and did not depend on the keying at all. The five Modelo 303 cases named above are real; only the explanation for the gate's silence was wrong.

## Verification

    uv run --no-sync python <scratch>/probe_m303_epochs.py
          2023: 174 numbered boxes, sheets=('variable','1581','1706','1017','998','1523','823')
    2024-early: 174 numbered boxes, sheets=('variable','1581','1706','1017','998','1523','823')
    === 2023 -> 2024-early ===
      BOX OFFSETS : 0 of 174 shared boxes moved
      PAGE LENGTHS: IDENTICAL
      OCCUPANCY   : 4 retired into reserved, 0 reserved->real
          RETIRED DP30302 offset 1110 ... -> 'Reservado para la AEAT'
          RETIRED DP30302 offset 1116 ... -> 'Reservado para la AEAT'
          RETIRED DP30302 offset 1236 ... -> 'Reservado para la AEAT'
          RETIRED DP30302 offset 1242 ... -> 'Reservado para la AEAT'

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py -p no:randomly -q -rA
    5 passed, 1 failed
    FAILED ...::test_no_revision_spans_a_design_relayout

The probe reads the bundled workbooks through the shipped `extract_record_design_workbook` parser, the same one the gate uses, and asserts each design parsed to something non-empty before comparing, so an unreadable design fails loudly rather than reporting as identical. The gate run supplies the independent corroboration: its own occupancy signal reports the same 4 retired slots at the same offsets from a separately written comparison.

## Notes

**The two documents named different pairs with the same label.** The gate keys its per-signal inventories on the year parsed from a filename and keeps the first design by filename sort, so its "2023/2024" boundary is 2023 against whichever 2024 half sorts first. The finding survives that ambiguity: the four slots are reserved in both 2024 halves, so 2023 against either half reports the same four retirements. A reader must not generalise from this that the gate's year labels are safe.

**Divergence recorded rather than silently overridden.** The sub-year decision record's Considerations state that 2023 to 2024-H1 is identical on four counts and its Implementation states that exactly one pair carries an identical export layout by construction. Both are overtaken by this measurement. The record's mechanism ruling, the period-token partition, is untouched and still governs.
