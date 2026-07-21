---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S05'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

# Defer repository-backed counterpart provider enrollment until a ledger or purchase-evidence binding trigger is approved

## Scope

- `src/aeat/application/aggregation/_counterpart.py`

## Description

- Run RAG code and vault discovery for counterpart provider enrollment, reserved source kinds, and the ADR trigger.
- Confirm `CounterpartAggregationSourceResolver.owned_sources` is narrowed to `ledger_transaction` and `purchase_invoice_evidence`.
- Confirm `RESERVED_SOURCE_KINDS` still contains `ledger_transaction` and `purchase_invoice_evidence`.
- Confirm current M347 summary bindings do not declare either reserved source.
- Run focused counterpart, mesh-parity, enrollment-status, and source-boundary gates for the reserved-provider disposition.

## Outcome

Repository-backed counterpart provider enrollment remains deferred by design, not missing implementation:

- The accepted counterpart-provider ADR requires provider enrollment to co-land with a registry revision declaring `ledger_transaction` or `purchase_invoice_evidence`.
- Current M347 summary support is invoice-owned and does not declare those reserved sources.
- `CounterpartAggregationSourceResolver` is pre-enrollment-narrowed to the two reserved kinds.
- The source mesh still classifies those two kinds as `RESERVED_SOURCE_KINDS`, not enrolled and not deferred.

Verification passed:

`uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests/test_per_modelo_service.py -k "counterpart" src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py src/aeat/application/modelo/tests/test_source_boundary_and_enrollment.py -k "reserved or counterpart or deferred or foreign_asset" --tb=short`

Result: 22 passed, 31 deselected.

No code changes were required. No code-fixer agent was dispatched.

## Notes

This row is intentionally a formal deferral. A future implementation may start only when the accepted ADR trigger fires and the registry/provider/correctness-gate changes are scoped to co-land.
