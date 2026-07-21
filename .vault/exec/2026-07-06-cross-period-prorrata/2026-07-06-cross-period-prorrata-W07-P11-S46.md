---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-08'
step_id: 'S46'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# implement the prorrata_regularizacion live source resolver with binding values, unresolved diagnostics, and provenance from the register or stamped prior observation plus current-year registry values

## Scope

- `src/aeat/application/calculations/_prorrata_regularizacion.py`
- `src/aeat/application/calculations/__init__.py`
- `src/aeat/application/calculations/tests/`

## Description

- Re-ran live plan status and confirmed `W07.P11.S46` was the next open step with no missing exec records.
- Re-grounded the resolver scope through semantic search for prorrata live source materialisation, current-year registry values, and carry-style source resolvers before editing.
- Added `ProrrataRegularizacionSourceResolver` as an unenrolled source-mesh resolver for `prorrata_regularizacion`.
- Resolved declared binding ids from the registry selector output instead of hard-coding modelo-specific wiring.
- Consumed current-year registry materialisation values for deductible total, declared prorrata volumes, and definitive percentage; missing or unresolved current-year casillas now mark declared bindings unresolved with diagnostics.
- Resolved the provisional percentage from the encrypted prorrata register first, then from a stamped prior-year Modelo 303 settlement observation only when the shared revision-carry gate reconfirms the source stamp.
- Returned binding values for Modelo 303 casilla 44 and Modelo 390 annual regularizacion targets through the existing pure regularizacion projection, with current-year and carry-source provenance rows.
- Exported the resolver from the application calculations facade without enrolling it in the live source mesh.
- Added focused real-behavior tests using the bundled AEAT Manual IVA prorrata oracle, the real secure prorrata register repository, and the real calculation observation repository.
- Reviewed the diff for accidental mesh enrollment, source-kind taxonomy changes, carry-stamp weakening, formula duplication, and silent missing-value behavior.

## Outcome

- S46 is complete: the live resolver exists, produces binding values and unresolved diagnostics, and carries provenance from current-year registry values plus either the register or a stamped prior observation.
- The implementation introduces no new source kind, resolver taxonomy, or validator convention, and it does not edit `_source_mesh.py`; enrollment and deferred carve-out removal remain owned by `W07.P12.S47`.
- Close-review repair removed the premature `application.modelo` source-mesh call path so this step leaves the resolver provisioned and exported but not live-enrolled.
- Current-year values are supplied to the resolver by the S45 materialisation seam; the resolver does not recompute annual volumes or the definitive percentage.
- A missing provisional source now leaves the declared binding unresolved rather than fabricating zero.
- Self-review finding status: no open S46 implementation findings.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\calculations\_prorrata_regularizacion.py src\aeat\application\calculations\__init__.py src\aeat\application\calculations\tests\test_prorrata_regularizacion_source_resolver.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion_source_resolver.py -n 0`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py src\aeat\application\calculations\tests\test_prorrata_regularizacion_oracle.py src\aeat\application\modelo\tests\test_prorrata_regularizacion_advisory.py src\aeat\application\modelo\tests\test_prorrata_regularizacion_source_timing.py -n 0`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_iva_compensation_relation_prefill.py -n 0`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_source_boundary_and_enrollment.py src\aeat\application\modelo\tests\test_unresolved_binding_diagnostics.py -n 0`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\domain\calculations\registry\tests\test_binding_source_kind_taxonomy.py src\aeat\application\modelo\tests\test_binding_source_kind_mesh_parity.py -n 0`.
- The rolling cross-period-prorrata audit file already contains uncommitted S44/S45 review content, so this S46 evidence was kept in the exec record instead of appending to that shared WIP document.
