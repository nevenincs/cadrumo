---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:27859445d52a8d91e90b7e7571502d6d6e90cb55677bf0e7985d9af8d13e4179'
step_id: 'S03'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Reconcile this plan's per-revision row set against the boundary set and the reachable window

## Scope

- `.vault/plan/2026-08-08-aeat-design-relayout-boundary-plan.md`

## Description

- Re-run the span gate at HEAD and take its live boundary set rather than any document's snapshot of it.
- Compare the row set against the computed reachable window and against the measured epoch count.
- Reconcile the diverging rows through the plan step verbs, never by hand-editing a checkbox or a row.
- Correct the one Phase prose line the measurement contradicted, through the owning body-edit verb so the body stamp stays honest.

## Outcome

The live gate at HEAD names **fourteen boundaries across four revisions**: Modelo 200 `2024-y-siguientes` spans 1 and needs 2, Modelo 303 `2009-y-siguientes` spans 4 and needs 5, Modelo 303 `2023-y-siguientes` spans 3 and needs 4, and Modelo 390 `2010-y-siguientes` spans 6 and needs 7. Its two known understatements both hold: Modelo 303 `2023-y-siguientes` actually needs five revisions covering five epochs, and its labels are year-keyed so its "2023/2024" is 2023 against whichever 2024 half sorts first.

Five rows changed and two were added.

**Modelo 390 lost a revision.** The plan's five authoring rows mapped to filing years 2021 through 2025, which requires the earliest in-window year to be 2021. It is 2022: ejercicio 2021 prescribed on 2026-01-30, confirmed by the registry's own deadline window for that year rather than by inference. Under the corrected edge the modelo needs **four** revisions covering three in-window boundaries. `S31` was re-pointed to filing year 2022 as the window-edge revision, naming the year explicitly so the mapping cannot drift again. `S32` was **removed** and its identifier retired: its whole rationale was the 2021/2022 boundary, which now sits below the edge and is served by the refusal rather than by a split. `S33`, `S34` and `S35` were re-pointed to filing years 2023, 2024 and 2025-onward respectively, each naming its year and its boundary evidence, because as written they were positional and a removal above them would have silently shifted their meaning.

**Modelo 303's row count is unchanged and two rows gained a constraint.** The window edge at 2022 is exactly what the plan assumed, so the five excluded boundaries it named stay excluded and no row was added or removed for the window. But the 2023 and early-2024 designs are not layout-identical, so `S15` and `S16` were re-pointed to state that the four Regimen Simplificado employee-count slots at sheet DP30302 offsets 1110, 1116, 1236 and 1242 are real in 2023 and reserved from early 2024, and that no pair may share a copied fragment tree.

**Two rows were added for work the measurements exposed.** `W02.P04.S64` requires each Modelo 303 revision to re-derive its total-formula operand lists from its own design rather than copying the newest expression backwards, since box 27 gains operands 167 and 170, box 69 gains operand 108, and box 71 gains a subtracted operand 112. `W01.P02.S65` requires the reserved-to-real occupancy direction to be asserted once the inventory is re-keyed on the design file, because that re-keying gives the direction five positive cases in Modelo 303 alone and so retires the gate's recorded rationale that such an assertion would ship vacuous.

**One Phase prose line was corrected.** The authoring Phase described five revisions covering four design epochs with the layout-identical pair implied. It now states five epochs, no duplicate layout, and the reason.

The filing years the reconciled scope leaves **refusing** rather than correctly exported are unchanged for Modelo 303 and widen by one year for Modelo 390. Modelo 303 refuses filing years 2009 through 2021. Modelo 390 refuses 2010 through **2021**, where the pre-reconciliation row set would have served 2021. Modelo 200 refuses nothing new, both its spanned years being in window. What the standing goal still asks for that this excludes is a correct export for every one of those years; after this plan they refuse by name instead.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py -p no:randomly -q -rA
    5 passed, 1 failed
    FAILED ...::test_no_revision_spans_a_design_relayout
    modelo 200 revision '2024-y-siguientes' spans 1 re-layout(s) and needs 2 revisions -- 2024/2025
    modelo 303 revision '2009-y-siguientes' spans 4 re-layout(s) and needs 5 revisions -- 2014/2015; 2016/2017; 2020/2021; 2021/2022
    modelo 303 revision '2023-y-siguientes' spans 3 re-layout(s) and needs 4 revisions -- 2023/2024; 2024/2025; 2025/2026
    modelo 390 revision '2010-y-siguientes' spans 6 re-layout(s) and needs 7 revisions -- 2017/2018; 2020/2021; 2021/2022; 2022/2023; 2023/2024; 2024/2025

    uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-08-08-aeat-design-relayout-boundary-plan.md
    [warning] PLAN022 line 0: Step canonical identifiers are not strictly monotonic in document order

Every mutation ran through `vault plan step edit`, `vault plan step remove` and `vault plan step add`, each reporting preserved prose blocks, and the prose line went through `vault edit --body-file`. The gate is still red and is expected to be: this Step reconciles the specification, it splits nothing.

## Notes

The PLAN022 warning is the documented insert-between shape rather than a defect: the two added rows took the next-available canonical identifiers 64 and 65 and sit inside earlier Phases, so document order diverges from identifier order by design. The retired identifier 32 is never reused.

**A later executor must recompute the window rather than read it here.** Modelo 303 filing year 2022 is only partially open and loses its 3T period on 2026-10-20, so the row set this Step reconciled has a shelf life.
