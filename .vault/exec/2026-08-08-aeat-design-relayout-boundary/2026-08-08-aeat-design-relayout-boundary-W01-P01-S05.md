---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9be27ac13116d771f0b513fa9bae6b05ab97194a5847d5f83c2f401bee0bb2d6'
step_id: 'S05'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Settle and record what a split must not change across a re-layout boundary

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`

## Description

- Diff the AEAT box-number set on each side of every in-window Modelo 303 boundary for additions, removals and numbers re-used for a different concept.
- Read the registry's own casilla id, formula id and continuidad stamp schemas to establish which of them are box-derived and which are semantic.
- Sweep every continuidad evolution record in the registry for a reference to a revision id this campaign retires.

## Outcome

The ruling has three parts and each is measured rather than assumed.

**Casilla ids carry unchanged, and a split must not renumber.** Across all four in-window Modelo 303 boundaries, **zero box numbers are removed and zero are re-used for a different concept**. Movement is purely additive: eight boxes appear at the mid-2024 boundary (108, 111, 165 through 170) and one at the 2025 to 2026 boundary (112). Modelo 303's registry casilla ids are the AEAT box numbers for the numbered family, so a successor revision inherits every predecessor id at the same identity and merely gains rows. Any renumbering would be the campaign's own invention, not AEAT's, and would corrupt every cross-year carry keyed on the id.

**Formula ids carry unchanged, but formula EXPRESSIONS must not.** The formula ids are box-derived rather than revision-derived, of the shape `modelo-303-dr303-<box>-projection`, so they survive a split unchanged. The expressions do not. Three total formulas gain operands across the in-window boundaries, and in every case the box number, the concept and the description prefix are identical while the operand list grows: total cuota devengada in box 27 gains operands 167 and 170 at the mid-2024 boundary, resultado de la autoliquidacion in box 69 gains operand 108 at the same boundary, and resultado in box 71 gains a **subtracted** operand 112 at the 2025 to 2026 boundary. Copying the newest expression backwards into an earlier revision would sum boxes that design has no room for; copying the oldest forwards would silently drop a declared quantity from a total, which is the under-declaration shape this project refuses. Each revision must re-derive its expressions from its own design. A new row was opened in the authoring Phase for exactly this.

**Continuidad stamps are keyed on a semantic continuidad id, not on the casilla id, but Modelo 303's numbered family derives that id from the box number.** The mechanism is the `casilla_continuidad_evolutions` fragment, whose rows carry a `continuidad_id` plus a `from_revision` and `to_revision` naming revision ids. Modelo 303's semantic casillas carry genuinely renumbering-immune stamps such as `iva-cuota-repercutida-general`; its numbered casillas carry `dr303-<box number>`, which is box-derived and therefore **immune only because nothing renumbers**. Given the measured zero removals and zero re-uses, the stamps are stable across every boundary this campaign splits. That is safety by measurement, not safety by construction, and a future boundary that retires or re-uses a box number would break it.

**No continuidad reference is left dangling by this split.** Twenty-six evolution rows in the registry name a revision id string this campaign retires, and **all twenty-six belong to Modelo 180**, whose own revision happens to be named `2023-y-siguientes`. The revision-id namespace is per-modelo, so none of them refers to Modelo 303. Modelo 303, Modelo 390 and Modelo 200 declare no continuidad directory at all today, so the split creates no repair obligation and the Modelo 180 rows must not be touched.

One naming hazard is flagged rather than resolved, because resolving it belongs to the authoring rows. Two formula ids in the modulos engine fragment embed a bare year, `modelo-303-2023-modulos-iva-cuota-devengada` and its cuota-derivada sibling. Under one open-ended revision that year was merely the revision's opening year; after the split it reads as scoped to filing year 2023 while in fact being inherited by every successor epoch. The authoring executor must decide whether to carry the id unchanged and accept a misleading name or re-derive it, and must not discover the question mid-authoring.

## Verification

    uv run --no-sync python <scratch>/probe_m303_epochs.py
    === 2023 -> 2024-early ===      BOX SET : 0 added []  |  0 removed []
    === 2024-early -> 2024-late === BOX SET : 8 added ['108','111','165','166','167','168','169','170']  |  0 removed []
    === 2024-late -> 2025 ===       BOX SET : 0 added []  |  0 removed []
    === 2025 -> 2026 ===            BOX SET : 1 added ['112']  |  0 removed []

    uv run --no-sync python <scratch>/probe_desc.py
    [27] 2024-early: ... Total cuota devengada ( [152] + [03] + ... + [26] ) [27]
    [27] 2024-late:  ... Total cuota devengada ( [152] + [167] + [03] + ... + [170] + ... + [26] ) [27]
    [71] 2025: Resultado - Resultado ( [69] - [70] + [109] ) [71]
    [71] 2026: Resultado - Resultado ( [69] - [70] + [109] - [112] ) [71]

    continuidad rows naming one of those revision-id strings, by modelo: {'180': 26}
    c22__c111.toml casilla ids: 57 continuidad_ids: 54
       first 6 pairs: [('22','dr303-22'), ('23','dr303-23'), ('24','dr303-24'), ...]

The three re-described boxes were read in full rather than truncated, which is what distinguishes an operand-list change from an identity change; truncated at seventy characters all three read as unchanged and the finding would have been missed in the opposite direction.

## Notes

Neither accepted decision record rules on this question, so nothing here diverges from either. The ruling is recorded before any revision is authored, which is what the plan required rather than treating continuity as an assumption.

The Modelo 390 side of this question is **not** settled here and the scope did not include it. Its casillas are semantic ids rather than box numbers, so a number-keyed diff reports hundreds of false absences there and the same method does not transfer. The Modelo 390 authoring rows must settle their own carry question before authoring.
