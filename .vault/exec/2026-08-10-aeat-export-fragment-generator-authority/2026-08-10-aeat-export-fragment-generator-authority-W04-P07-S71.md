---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:5149c773556bafe879d2df19127cdfb28e91e3c1221376074541a0c3f019bde5'
step_id: 'S71'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author and review the Modelo 303 2026-epoch semantic map and source-bound render profile, exact-bijecting all 417 fixed-record anchors plus the 13 DP30300 prefix anchors, 430 in total, each to its one canonical typed authority. Review by hand every anchor added over 2025 and every delta that moves a semantic home rather than an offset. Of these anchors 142 are nonnumbered DP30302 simplified-regime anchors whose projection endpoint declarations S63 supplies, so this row cannot close before S63 lands and its DP30302 share must be re-counted against the post-S63 declaration index. Do not inherit the 2023 or 2024-early amendment-evidence assignment: from 2024-late onward DP30303 ordinal 29 declares a rectificativa self-assessment with additional rectification-motive fields, which moves the semantic home between the complementaria and rectificativa amendment-evidence producers rather than shifting an offset, so that region is hand-reviewed per epoch

## Scope

- `dev/registry/mappings/modelo_303/2026/`
- `dev/registry/render_profiles/modelo_303/2026/`

## Status

Authored, not closed. The row stays unchecked; the owning coordinator closes
rows in this chain.

## Description

- Author the 2026 mapping fragment set from the reviewed 2025 homes.
- Re-derive every ordinal from the 2026 design rather than carrying any across.
- Hand-review every anchor exact correspondence refuses.
- Move the no-activity marker from a shared anchor fact to a per-epoch one,
  because this design relocates it.
- Enrol the 2026 census expectation and reviewed surface, chained to 2025.

## Outcome

The 2026 epoch exact-bijects 430 anchors: 417 fixed-record anchors plus the 13
DP30300 prefix anchors, matching the contracted count. Per record the fixed
anchors are DP30301 89, DP30302 166, DP30303 38, DP30304 43, DP30305 68 and
DP303DID 13. The nonnumbered DP30302 simplified-regime share measures 142,
matching the contracted share. The mapping is one-to-one in both directions
with no duplicate, unmapped or extraneous anchor.

Of 417 anchors, 407 carried their reviewed home across by exact declaration
correspondence and 10 were hand-reviewed.

A new identification flag records entitlement to deduct the advance payment on
fuel deliveries following the end of the non-customs deposit regime. Its
producer key already existed in the closed filing vocabulary and had never had
an anchor, so this design gave standing vocabulary its home rather than
requiring new vocabulary. A new resultado box carries the matching advance
payment attributable to the State, summed from the dependent filings the
autoliquidación covers, and enters the result formula. The result box keeps its
casilla home, its stated formula having only gained the new term. Two reserved
runs absorb the space those additions took, one of them merging a run the
previous design carried mid-block. Five prorrata activity projections keep
their homes while their slots widen by one byte, which restates the code
table's size rather than changing meaning.

Two semantic homes are introduced and none retired; everything else is a pure
offset shift, correctly silent under identity comparison.

The whole suite reports 159 passed with no failures and no errors across all
five epochs. Lint, format and type checks pass.

## Method

Reviewed homes cross an epoch boundary only where both designs declare the slot
identically on the six axes the design itself states: record, label, stated
content, width, AEAT type and validation. Ordinal, row and offset are excluded,
because a re-layout moves those while changing nothing about meaning. Where one
declaration repeats inside a record -- the module slots the design distinguishes
only by repetition -- occurrences correspond in order, and only when both epochs
declare the same number of them; an unequal count is a multiplicity change and
becomes a review question instead of being paired through. Everything else
refuses into a hand-reviewed table, and the authoring pass writes nothing at all
if one anchor is unresolved, if a hand decision names an anchor the design does
not declare, or if any anchor is left uncovered. No positional matching, no
similarity scoring, no legacy tree consulted as an oracle.

That correspondence now lives in the census module as the single canonical rule,
so authoring and verification cannot hold different notions of the same slot.

## Notes

THE FINDING THAT MATTERS. This design relocates the no-activity marker, and it
was being asserted as a fact shared by every epoch at a fixed ordinal. The
shared table even carried a comment predicting that an epoch moving it would be
reporting a re-layout rather than a re-vocabulary. That is exactly what
happened: inserting the new resultado box and moving the rectification amount
to the head of the block shifted the marker by two ordinals. Had the ordinals
been carried across from the previous epoch instead of re-derived, the marker
and the whole rectification block behind it would have been written at the
wrong offsets on a real filing, with every count still reconciling. The
per-epoch hand review caught it; no count could have. The marker is now stated
per epoch, and this design declares its whole amendment-evidence block at its
own ordinals rather than inheriting any of them.

That is the general lesson for any further epoch: a count proves coverage,
never correctness of placement, and an ordinal is a fact about one design only.

A second gate was added while authoring this epoch, after measuring that the
introduced-and-retired home review reaches only the homes an epoch changes at
its boundary. Because that review compares set membership, exchanging two homes
an epoch inherits changes neither set and passed silently, as did the census
totals. Every anchor the two designs declare identically must now carry the
same home in both. Measured across all four epoch transitions, 377, 375, 383
and 407 anchors correspond and none changed home, so the invariant holds with
no exception table.

No published revision tree was touched, no review status was promoted, and no
home was invented: every anchor resolves to an authority the registry revision
already declares. The trailing-period grammar fix that unblocked this epoch is
recorded against the preceding row, which carries its five-epoch control.
