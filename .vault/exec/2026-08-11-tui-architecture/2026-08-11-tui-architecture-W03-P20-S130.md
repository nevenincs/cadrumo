---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:13b5ac48b40d0fbfac7104eaca65dcc98c39bf9dc7ed22fb481933e3b401e4c7'
step_id: 'S130'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove strict Workspace round trips, exhaustive manifest coverage, exact ModeloWorkReview/readiness/closure parity, admission-specific contributor sets, exact-one-native-capture behavior, immutable or snapshot-isolated captures including mutation-after-capture isolation, unchanged owner generations, epoch/ABA/cross-incarnation refusal, locale behavior, bounded non-retention, forbidden lower-layer ModeloWorkspace imports, and a Vaultspec-RAG-plus-exact census that fails duplicate, legacy, shim, alias, fallback, bridge, or parallel Workspace authorities

## Scope

- `src/cadrumo/application/modelo/tests/test_workspace_projection.py`

## Changes

- `A` `src/cadrumo/application/modelo/tests/test_workspace_projection.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_projection.py -m integration -q -n0` -> `pass` (8 passed)
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/tests/test_workspace_projection.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/tests/test_workspace_projection.py` -> `pass`

## Notes

Read the Step's twelve named properties against existing coverage BEFORE
writing anything, the same discipline S129's census used. Six were already
solidly proven elsewhere and are cited rather than duplicated: exhaustive
manifest coverage (`test_workspace_manifest.py`, 21 tests); epoch/ABA/
cross-incarnation refusal and unchanged owner generations
(`test_workspace_producers.py`); locale behavior and bounded schema-facet
pagination (`test_workspace.py`); complete `ModeloWorkReview` parity against
its sole public producer (S128 remediation, `test_workspace.py`); and
readiness parity (`graded_snapshot_readiness` pass-through, S128,
`test_workspace.py`).

The new file `test_workspace_projection.py` carries the six genuinely
missing proofs, each specific to the ASSEMBLED result rather than a piece:

1. Strict round trip plus an anti-tautology mutation proof for both
   `ModeloWorkspaceStaticInspectionResultV1` and
   `ModeloWorkspaceGradedSnapshotResultV1` -- a plain equality round trip
   already existed; deleting a required nested field from the serialized
   payload and proving reload refuses did not.
2. Admission-specific contributor-set exactness: static (4) is a strict
   subset of graded (6), the two extra are exactly CALCULATION and
   BOUNDED_REVIEW, and each real assembled result's own `.contributors`
   matches its admission's canonical function output.
3. Mutation-after-capture isolation, targeting a field the projection
   demonstrably reads and asserts against (`WorkUnit.state`, reflected in
   `ModeloWorkspaceResolvedTargetV1.work_state`) rather than one it never
   touches.
4. Exactly-one-native-capture for the CALCULATION and BOUNDED_REVIEW ports,
   proven with a spy that wraps the real bound `capture_projection_with_epoch`
   method and counts invocations while still executing the genuine
   implementation -- not a mock, since no behaviour is replaced.
5. A forbidden-lower-layer-import architecture boundary: no tracked file
   under `domain/` or `adapters/` may import any Workspace assembly, model,
   producer, or manifest symbol.
6. A codified Vaultspec-RAG-plus-exact census against a duplicate or
   parallel Workspace authority: an AST walk over every tracked
   `application/modelo` production module asserting each canonical
   assembly/model/producer entry point is defined in exactly the one module
   that owns it.

CANNOT BE PROVEN, reported rather than fabricated: "closure parity". No
`graded_snapshot_closure`-equivalent function exists anywhere in
`workspace.py`, and neither `resolve_static_inspection_result` nor
`resolve_graded_snapshot_result` ever populates `registry_closure_limbs`
(stays at its `()` default) or `readiness` (stays `None`) on the assembled
projection. S128's own exec record already recorded this as deliberately
deferred ("readiness/closure ports remain genuinely OPTIONAL"). There is
nothing to compare parity against; this should be tracked as its own
follow-up Step rather than silently marked done or silently dropped.

Resolved one ambiguity by reading rather than guessing: "bounded
non-retention" appears in the governing ADR only inside a C3/C4
interface-cohort receipt list (`sensitive_non_retention`) for the LATER TUI
operation-handoff phase, with no implementation to test yet -- the same
shape as the closure gap above. Read this Step's "bounded non-retention" as
the pagination-cap property instead (already covered by the existing
7-page cursor round-trip and stale-cursor-refusal tests in
`test_workspace.py`), reported to the team lead before building on that
reading.

Two real bugs surfaced by actually RUNNING the tests rather than trusting
the first draft, both fixed before landing:
- The original mutation-after-capture test mutated
  `CalculationRevision.casilla_values` on the SAME `calculation_revision_id`
  after capture. `calculation_revision_id` is itself content-derived from
  `casilla_values`, so the real repository refused the mutated save with a
  `ValidationError` before the intended assertion ever ran -- a genuine,
  useful finding about the domain's own content-addressed identity, not a
  test bug to route around silently. Proved that refusal directly with its
  own assertion, then retargeted the isolation proof at `WorkUnit.state`, a
  genuinely mutable field the resolved target demonstrably reads.
- The forbidden-lower-layer-import scan first used a raw substring search
  for `"ModeloWorkspace"`, which false-positived on
  `test_authority_native_capture.py:834-835` -- that test legitimately
  asserts the string `"ModeloWorkspace"` is ABSENT from the registry
  authority's own source, the mirror proof of this exact boundary from the
  other side, so the needle appeared inside a Python string literal in an
  assertion rather than an import. Replaced with an AST walk that inspects
  actual `Import`/`ImportFrom` nodes.

This module's first draft landed via a peer's shared-index commit
(`c9821a78de`) while still under construction; the two fixes above landed
as a separate, explicit-pathspec follow-up commit (`cff36304ad`) once both
failures were found and corrected by running the suite, not by reading it.
