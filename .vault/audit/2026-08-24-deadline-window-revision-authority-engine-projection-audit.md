---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6f55c898f6ed4aa58241c319090852a09a8737327c524189d6865a1256c8e961'
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

### engine-projection-remediation | low | APPROVE â€” HIGH and MEDIUM findings closed

Independent remediation review approved the current S26 slice with no HIGH or
MEDIUM findings. The expected projection now comes from the public canonical
`ValidatedRegistryAuthority.deadline_windows`, `applicable_filing_schedules`, and
`evaluate_profile_conditions` surfaces; it never calls the engine's private
obligation builder or private applicability helpers. Filing years come directly from
`authority.catalogues.supported_filing_years.years`.

Exact `Counter` equality preserves omissions and multiplicity, and an explicit mutation
control proves both a dropped applicable coordinate and a duplicate emitted coordinate
raise. The exact M303 2025 quarterly and REDEME monthly assertions and qualified-M210
pre-calculation exclusion remain. Vaultspec RAG followed by exact-symbol confirmation
found no selector, resolver, parser, cadence authority, supported-year horizon, deadline
catalogue, or deduplication path introduced by the remediation. Ruff passed and the
full focused engine module passed 42 tests.

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

Both recommendations are implemented and independently approved. Close S26.
## Final remediation re-review

APPROVE. The current remediation independently derives expected periodic coordinates from the bundled validated authority, the canonical supported-filing-year catalogue, and the public filing-schedule and profile-condition evaluators. It no longer calls `_obligation_for_window` or any other private engine applicability helper, and it declares no local year horizon.

Exact Counter equality compares the entire applicable periodic projection with emitted periodic coordinates. The drop and duplicate mutation controls prove the assertion fails in both directions; the filter that separates periodic output is itself grounded in the complete authority coordinate set. The original Modelo 303 2025 assertions still require exactly four quarterly and twelve monthly rows.

Vaultspec RAG plus exact-symbol confirmation found no deduplication, selector, cadence map, parser, supported-year horizon, or deadline catalogue added to the engine or remediation. Qualified M210 windows remain excluded from the pre-calculation engine and owned by the post-calculation plazo resolver. No findings remain open.
