---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:5b6814d951dd280114f28ff3b31e4139c9e73c376db7566b39d3599bd9833eed'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
  - "[[2026-08-24-deadline-window-revision-authority-adr]]"
---
# `deadline-window-revision-authority` audit: `engine projection`

## Scope

Reviewed commit `81f398cb0d` limited to `DeadlineEngine` and its engine regressions against the accepted deadline-window revision-authority plan. Vaultspec RAG semantic discovery was paired with exact confirmation for projection, selection, cadence, qualifier, and deduplication authorities.

## Findings

No findings. `_obligation_for_window` now rejects any resultado- or tipo-renta-qualified row before static profile applicability, correctly keeping M210 qualified plazo variants out of the pre-calculation schedule. The engine continues to consume `ValidatedRegistryAuthority.deadline_windows` directly and adds no deduplication, revision selector, period parser, cadence map, or local deadline catalogue.

The Counter regression is multiplicity-sensitive: its expected Counter is built from each applicable authored periodic projection row, while actual counts come from the emitted schedule, so a dropped row, duplicated emission, or deduplication of repeated projected coordinates would fail. Its global multiplicity assertion also refuses unexpected duplicate schedule coordinates. The dedicated Modelo 303 regression independently preserves the original exact 2025 cadence contract of four quarterly or twelve monthly obligations.

Qualified M210 exclusion is explicitly pinned, and the existing ambiguity and qualified post-calculation selection remain owned by the canonical plazo resolver rather than the engine.

### engine-projection | high | Fleet parity derives expected applicability through the implementation under test

On re-review, `test_compute_preserves_each_applicable_authored_periodic_coordinate_once`
calls the private `DeadlineEngine._obligation_for_window` helper to decide which
authority rows belong in `expected`, while `DeadlineEngine.compute` calls that
same helper to produce `actual`. If the helper wrongly excludes an applicable
monthly or quarterly row, both sides omit it and the test remains green. The
test checks loop preservation and output uniqueness, but it does not prove the
Step's stronger claim that every applicable authored periodic coordinate is
emitted exactly once. The focused selection passes (12 tests), but the shared
implementation oracle leaves the completeness gate tautological at the engine
applicability boundary.

### engine-projection | medium | Fleet coverage redeclares the supported filing-year horizon

The fleet test parametrizes `range(2022, 2027)` locally instead of consuming the
registry's canonical `supported_filing_years` catalogue. Vaultspec RAG located
that catalogue under the validated registry authority, and an exact-symbol
sweep confirmed that it is already loaded and exposed there. The local range is
a second supported-year horizon: a catalogue extension can leave this alleged
fleet test green while the new year is never exercised. This conflicts with the
ADR requirement that deadline completeness consume the shared temporal-coverage
declaration and add no deadline-specific horizon.

No production redeclaration was found. The engine consumes the validated
authority projection without deduplication, and its qualifier gate correctly
keeps resultado/tipo-renta-qualified M210 rows out of the pre-calculation
schedule while the sole qualified resolver remains in
`domain/deadlines/_plazo.py`.

## Recommendations

Approve `W03.P11.S26` without production changes.

The approval above is superseded by the two re-review findings. For the high
finding, build expected periodic coordinates independently from validated
registry rows plus the canonical public filing-schedule applicability primitive,
and add a mutation proof showing that suppressing one otherwise applicable
engine projection makes the test fail. Do not call the engine's private
obligation-construction helper from the oracle.

For the medium finding, parametrize the test from the validated authority's
canonical supported-filing-year catalogue. Keep the semantic-coordinate
`Counter` comparison so multiplicity remains visible; do not replace it with a
set or dictionary projection.
