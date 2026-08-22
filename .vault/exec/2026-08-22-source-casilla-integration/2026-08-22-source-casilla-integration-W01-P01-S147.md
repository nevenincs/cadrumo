---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:95e0a8c43ad2639a2496d97e3a549bd53cd7dfc63b2b9b06f2d39b2274f99f1c'
step_id: 'S147'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# make persisted source provenance internally coherent, identity-bearing, unambiguous, and strictly typed

## Scope

- `src/cadrumo`

## Description

- Require explicit coherent binding-source identity on application and persisted provenance rows.
- Hash complete source provenance into calculation revision identity in deterministic order.
- Restrict composite resolution owners to the closed `CompositeSourceResolverId` type.
- Refuse rival persisted resolver rows and incoherent source-kind matches in connectivity authority.
- Replace the local cross-period composite fixture with real typed resolver resolutions and composition.
- Prove resolver and fingerprint mutations change revision identity and legacy identity omissions fail closed.

## Outcome

Persisted source provenance is now internally coherent, identity-bearing, unambiguous, and typed. Binding-backed rows require exact `source_kind` and `binding_source` equality; non-binding rows state `binding_source=None` explicitly. Revision identity canonicalizes resolver, binding source, source kind, source reference, fingerprint, and dependency treatment independent of row order. Connectivity proof rejects rival resolver rows for one source identity.

## Notes

Concurrency incident: while focused tests were running, another shared-worktree process committed the S147 source changes in mixed commit `03177b3da8` together with unrelated registry and locale content. The plan insertion had already landed separately in `4577491fc6`. No rewrite, reset, revert, or recommit of another agent's content was performed. This deviates from the one-Step/one-source-commit contract; this record and the plan-checkbox commit restore truthful traceability without claiming commit-topology compliance.

S147-owned paths within `03177b3da8` are `src/cadrumo/adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py`, `src/cadrumo/application/aggregation/__init__.py`, `_atribucion_member.py`, `_foreign_assets.py`, `_modelo_bindings.py`, `_oss_ioss.py`, `_source_mesh.py`, `_withholding_source.py`, `tests/test_source_mesh.py`, `src/cadrumo/application/calculations/_bienes_inversion_regularizacion.py`, `_iva_wallet_reconciliation.py`, `_m303_regimen_simplificado_annual_summary.py`, `_multi_year.py`, `_prorrata_regularizacion.py`, `_relation_prefill.py`, `src/cadrumo/application/invoices/_source_resolver.py`, `src/cadrumo/application/modelo/_borrador_binding.py`, `_profile_binding.py`, `_revision_persistence.py`, `tests/test_local_cross_period_carry.py`, `tests/test_source_provenance_projection.py`, `src/cadrumo/application/registry/_source_connectivity_authority.py`, `tests/test_source_connectivity_authority_contract.py`, `src/cadrumo/domain/modelos/_calculation_revision.py`, `tests/test_calculation_revision.py`, and `src/cadrumo/entrypoints/cli/tests/test_modelo_payloads.py`.

Pre-change collection found 60 tests on the primary schema surfaces. Final focused verification passed 83 selected tests with 28 integration-marked tests deselected by repository policy. Ruff passed across the changed application, domain, adapter-test, and CLI-test surfaces. Compilation/import succeeded during test collection. Vault closure retained only the campaign's pre-existing ordering/index/body-section warnings.
