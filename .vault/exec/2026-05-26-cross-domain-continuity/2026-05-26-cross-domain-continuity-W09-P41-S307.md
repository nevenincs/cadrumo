---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S307'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R8-NURIA-HIGH M184 atribucion de rentas calculation path missing

## Scope

- `bindings require atribucion_member source which has no CLI entry`
- `sociedad civil and comunidad de bienes contribuyentes cannot file the informative declaration from the CLI`
- `add ledger ordering for entity members (socios) and an atribucion_member source resolver`
- `src/aeat/_data/registry/aeat/modelos/184/`

## Description

- Run required RAG grounding query: `S307 M184 atribucion_member source resolver sociedad civil comunidad bienes CLI calculation`.
- Run vault RAG grounding query for `S307 S323 M184 attribution entity socios atribucion_member`.
- Record the governing ADR for promoting `atribucion_member` out of deferral after source-mesh research showed the deferral required an explicit design decision.
- Add the `AtribucionMemberSourceResolver` that reads active attribution-entity profile socios, requires explicit `base_imponible_assigned`, canonicalises member order by NIF, and feeds observations through the existing detail-record resolver.
- Enrol `BindingSourceKind.ATRIBUCION_MEMBER` in the calculation source policy and remove it from source-mesh deferrals.
- Extend the committed user-profile schema with the narrow `attribution_entity_socios.base_imponible_assigned` money field so M184 can report an assigned base without deriving it from share percentage.
- Update source-boundary, enrollment, schema, and detail-row behaviour tests to cover complete socios, sorted member rows, and missing-base diagnostics.

## Outcome

- M184 calculation now resolves attribution-member row binding values and typed `Modelo184MemberRow` detail rows from real profile facts for sociedad civil and comunidad de bienes attribution entities.
- The resolver refuses incomplete socio rows with a `source_issue` diagnostic and does not fabricate zero or share-derived base amounts.
- `atribucion_member` is promoted from deferred to enrolled while unrelated `related_party` and `refund` deferred sources remain deferred.
- Focused tests passed:
  `uv run --no-sync pytest src/aeat/application/modelo/tests/test_source_boundary_and_enrollment.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/domain/user_profile/tests/test_attribution_entity_schema_fields.py src/aeat/domain/user_profile/tests/test_schema.py -q`.
- Additional mesh/deferred tests passed:
  `uv run --no-sync pytest src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py src/aeat/application/modelo/tests/test_deferred_detalle_source_advisories.py -q`.
- Python lint passed on touched Python files:
  `uv run --no-sync ruff check src/aeat/application/aggregation/_atribucion_member.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/_source_mesh.py src/aeat/application/modelo/_calculation_source_policy.py src/aeat/application/modelo/_calculation_actions.py src/aeat/application/modelo/tests/test_source_boundary_and_enrollment.py src/aeat/domain/user_profile/tests/test_attribution_entity_schema_fields.py src/aeat/domain/user_profile/tests/test_schema.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py src/aeat/core/aggregation.py`.

## Notes

- The implementation intentionally adds only the member assigned-base profile fact required by M184. It does not implement the separate cross-profile M100 propagation described by W09.P41.S324.
- The shared worktree contains unrelated dirty files. This execution touched only the S307 resolver, schema, focused tests, ADR, exec evidence, plan row, and feature index.
