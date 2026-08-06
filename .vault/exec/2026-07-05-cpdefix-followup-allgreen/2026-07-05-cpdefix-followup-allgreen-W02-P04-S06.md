---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:03c391752e11d8170b5b67f13e081f744b4901ecc2ebf9589dee84dd207ff5e5'
step_id: 'S06'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

# Audit current deferred and reserved source-kind partitions for registry-declared but unenrolled sources

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Run RAG code discovery for deferred and reserved source-kind partitions.
- Read the application mesh parity, live missing-source, and registry source-enrollment gates.
- Run the focused source-partition gate suite.
- Extract the current committed-registry source inventory and compare it against live dispositions.

## Outcome

The current source-kind partition is healthy:

- Declared source kinds are all classified as `ENROLLED` or `DEFERRED` under the live mesh.
- No `RESERVED_SOURCE_KINDS` member is declared by the committed registry.
- Current reserved set: `ledger_transaction`, `purchase_invoice_evidence`.
- Current deferred set: `atribucion_member`, `bienes_inversion_regularizacion`, `donativo_donor`, `prorrata_regularizacion`, `refund_operation`, `related_party_operation`.

Verification passed:

`uv run --no-sync pytest -q -n 0 src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py src/aeat/application/modelo/tests/test_source_mesh_missing_sources.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py --tb=short`

Result: 25 passed.

The computed inventory reported:

- `declared_not_enrolled_or_deferred=` empty.
- `reserved_declared=` empty.

No code changes were required.

## Notes

This confirms the current allgreen campaign should not dispatch a source-enrollment fixer until a current deferred trigger or reserved-source promotion trigger fires.
