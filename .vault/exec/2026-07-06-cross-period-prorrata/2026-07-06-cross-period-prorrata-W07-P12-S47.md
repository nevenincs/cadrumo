---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S47'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# enroll prorrata regularizacion in live source mesh

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`
- `src/aeat/application/modelo/_calculation_actions.py`
- `src/aeat/application/modelo/_calculation_source_policy.py`
- `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`
- `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`
- `src/aeat/application/aggregation/tests/`

## Description

- Re-ran live plan status and confirmed `W07.P12.S47` was the next open step with no missing exec records.
- Re-grounded the step through semantic search for prorrata source-mesh enrollment, caller override disposition, and deferred carve-out removal before editing.
- Removed `prorrata_regularizacion` from `DEFERRED_SOURCE_KIND_TARGETS` and enrolled it in the application source-kind policy.
- Added `prorrata_regularizacion` to the caller-overridable carry tier, with conformance coverage through the precedence-ladder tests.
- Wired `_resolve_bucket_source_mesh` to run `ProrrataRegularizacionSourceResolver` after the normal mesh pass, using a no-persist registry materialisation of current-year prorrata values.
- Added staging-only zero defaults for the IVA-wallet-owned compensation binding so unrelated carry gaps do not abort prorrata materialisation.
- Preserved existing unresolved binding ids when the expected-missing safety net adds more unresolved ids.
- Added live source-mesh tests proving the M303 prorrata resolver produces the AEAT oracle binding value through the mesh without a caller compensation binding, and proving the M390 binding resolves from stamped Modelo 303 source-period observations.
- Updated stale prorrata enum/module wording so the source is no longer described as deferred.
- Ran the mandatory review pass; the review audit scaffold could not be created because the same-day feature audit file already exists with shared uncommitted WIP, so review outcome is recorded here instead of overwriting that file.

## Outcome

- S47 is complete for live application source-mesh enrollment: `prorrata_regularizacion` is no longer a deferred source kind, is in the enrolled source-kind disposition set, and has a real resolver invocation on the bucket source mesh.
- The M303 path resolves `modelo-303-prorrata-regularizacion-casilla-44` through the real mesh path, real registry engine materialisation, real encrypted prorrata register, and bundled AEAT oracle values.
- The M390 path resolves `modelo-390-prorrata-regularizacion-anual` from stamped Modelo 303 source-period observations rather than fabricating values from the M390 snapshot.
- No new source kind, resolver convention, validator convention, mock, stub, skip, xfail, or formula duplicate was introduced.

## Notes

- Verification passed: `uv run --no-sync ruff check` over `_source_mesh.py`, `_calculation_actions.py`, `_calculation_source_policy.py`, prorrata/bienes modules, and the touched source-kind/enrollment tests.
- Verification passed: source-kind taxonomy, mesh parity, precedence ladder, enrollment-status, and prorrata source-mesh enrollment pytest slice (32 passed).
- Verification passed: prorrata resolver/timing/oracle/advisory pytest slice and live source-mesh enrollment tests, including M303 and M390 paths.
- Verification passed: bienes-inversion calculation/advisory pytest slice (15 passed).
- Verification passed: source-boundary, unresolved-diagnostics, source-mesh calculation, bucket aggregation flow, and local cross-period carry pytest slice (41 passed).
- Review finding for W07 close review: M303 casilla `44` remains `input_kind = manual` in the registry, so the source-mesh binding value is produced but not yet consumed into persisted casilla output. This pre-existing S43/S47 boundary gap must be surfaced in `W07.P12.S49`; it was not silently fixed here because it requires a formula/target-consumption decision that avoids a cycle between the pre-regularizacion deductible subtotal and the casilla-44 regularizacion output.
