---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:499ea41db88d909c756e7caf90619b2b3115ecfd22050ac8fad91f6662ce9ba7'
step_id: 'S70'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author and review the Modelo 303 2025-epoch semantic map and source-bound render profile, exact-bijecting all 416 fixed-record anchors plus the 13 DP30300 prefix anchors, 429 in total, each to its one canonical typed authority. Review by hand every anchor added over 2024-late and every delta that moves a semantic home rather than an offset. Of these anchors 142 are nonnumbered DP30302 simplified-regime anchors whose projection endpoint declarations S63 supplies, so this row cannot close before S63 lands and its DP30302 share must be re-counted against the post-S63 declaration index. Do not inherit the 2023 or 2024-early amendment-evidence assignment: from 2024-late onward DP30303 ordinal 29 declares a rectificativa self-assessment with additional rectification-motive fields, which moves the semantic home between the complementaria and rectificativa amendment-evidence producers rather than shifting an offset, so that region is hand-reviewed per epoch

## Scope

- `dev/registry/mappings/modelo_303/2025/`
- `dev/registry/render_profiles/modelo_303/2025/`

## Status

Authored, not closed. The row stays unchecked; the owning coordinator closes
rows in this chain.

## Description

- Fix the trailing-period defect in the decimal and integer official-content
  grammars, which refused a money form both new designs write.
- Add permanent cases for bare-terminator content and for the tolerance not
  loosening.
- Author the 2025 mapping fragment set from the reviewed 2024-late homes.
- Hand-review every anchor exact correspondence refuses.
- Enrol the 2025 census expectation and reviewed surface, chained to 2024-late.
- Validate the existing 2025 render profile against the joined design.

## Outcome

The 2025 epoch exact-bijects 429 anchors: 416 fixed-record anchors plus the 13
DP30300 prefix anchors, matching the contracted count. Per record the fixed
anchors are DP30301 88, DP30302 166, DP30303 38, DP30304 43, DP30305 68 and
DP303DID 13. The nonnumbered DP30302 simplified-regime share measures 142,
matching the contracted share re-counted against the post-S63 declaration
index. The mapping is one-to-one in both directions with no duplicate, unmapped
or extraneous anchor. The render profile validates against the joined design
and carries the 2025 design identity and digest, which the census asserts
against the parsed design's own.

Of 416 anchors, 383 carried their reviewed home across by exact declaration
correspondence and 33 were hand-reviewed.

Three DP30301 tipo slots become mandated literals of zero. The design states a
plain constant for the reduced, recargo and super-reducido transitional rates
because those rungs expired, so the rate is a wire value rather than a computed
one. This follows the reviewed predecessor rather than inventing a rule: the
2024-late map already homes the identical shape, a tipo slot stating a plain
constant zero, as a literal while homing its neighbouring base and cuota to
casillas. Four base and cuota slots keep their casilla homes, having lost only
a gating annotation from their stated content. One recargo tipo keeps its
casilla home because the design states an enumeration there rather than a
constant, so the value is selected rather than mandated.

Four DP30302 anchors are reserved space, two of them new runs reclaiming the
relief block that the 2024 emergency measures had opened for one year only.
Sixteen DP30302 anchors carry the Superficie de horno module's new
multiplicity: each activity's single day count becomes four measure-and-day
pairs across the non-agricultural cohort's two slots. Both facts were already
declared repeating in the core projection vocabulary, so this is a multiplicity
change rather than new vocabulary requiring a core edit.

Five DP30305 anchors keep their prorrata activity projections unchanged; their
stated content only names a newer edition of the code table.

Sixteen semantic homes are introduced and seventeen retired. The retired set is
the three transitional rate casillas that become mandated literals, the twelve
relief facts the expiring measures took with them, and the two single day
counts the new sub-indexed pairs replace.

The grammar fix was proved a no-op on every epoch that already compiled, by
reverting both patterns at runtime from outside the repository: 2023,
2024-early and 2024-late compile 393, 393 and 413 fields under either grammar,
while 2025 and 2026 move from refusal to 416 and 417. The whole suite reports
159 passed with no failures and no errors. Lint, format and type checks pass.

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

The trailing-period grammar defect was fixed as part of this row rather than
worked around, because a green anchor count reached by dodging it would have
measured the wrong thing. Ownership of the module had briefly been split
between two agents; the naming change was the other agent's and has landed, and
the content grammar returned here.

The ruling on where the terminator belongs is the grammar, not the note peel.
The peel is named and contracted for one job, returning the stem plus the note
numbers it removed, so stripping a period there would mutate the stem while
reporting nothing and leave the peel's own accounting untestable. The same file
had already settled the question the other way for the constant and
boolean-enumeration patterns, which carry their own optional terminator;
leaving three of four numeric grammars tolerant and one strict is exactly what
let a design writing a money slot with a full stop refuse. The decimal
terminator is written as an alternation rather than a stacked optional, because
the bounded clause it sits beside already ends in a period and appending
another optional one would quietly admit a doubled stop no design writes.

Both patterns were fixed together. The integer one was not failing, but it
carried the identical defect and would have reopened this on the first design
writing an integer slot with a full stop.

Two permanent cases were added for the shape no test covered: one proving the
peel reports such content unchanged while the grammar reads it, and one proving
the tolerance did not loosen, refusing a doubled terminator, a spaced
terminator, trailing prose and an unnumbered note reference. The end-to-end
integer probe gained a bare-terminator suffix alongside its note-bearing ones.

No published revision tree was touched, no review status was promoted, and no
home was invented: every anchor resolves to an authority the registry revision
already declares.
