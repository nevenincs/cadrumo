---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S17'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add create behavior for bucket-scoped Modelo 145 communication records

## Scope

- `src/aeat/application/modelo`

## Description

- Add `M145CommunicationCreateCommand` and `M145CommunicationRecord` for bucket-local Modelo 145 communication creation.
- Persist records through the shared `SecureSnapshotRepository` using the centrally registered `M145_COMMUNICATION_RECORD_NAMESPACE`.
- Derive deterministic communication record ids from bucket, Modelo 145, communication year, period token, registry revision, and registry casilla values.
- Add list/read helpers that use the same secure repository factory as create, avoiding a parallel read path.
- Add real-runtime tests for secure persistence, idempotent create, communication versus variation period identity, prefix read-back, and registry casilla membership.

## Outcome

- `create_m145_communication_record()` now writes local Modelo 145 payer communication records into encrypted bucket-local storage and returns the existing record for an identical replay.
- The public create surface uses `communication_year`, `period_token`, and `field_values` vocabulary; it does not introduce a filing state, filed state, AEAT submission action, deadline, live-read, portal, or receipt surface.
- Field keys are checked against the active Modelo 145 registry revision. Required-field/type validation, export rendering, local delivered/completed transitions, bucket events, and service-level errors/logs remain assigned to later open steps.
- Verification passed:
  - `uv run --no-sync ruff check src/aeat/application/modelo/_m145_communication_records.py src/aeat/application/modelo/tests/test_m145_communication_create.py src/aeat/application/modelo/__init__.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py`
  - `uv run --no-sync pytest -q -n 0 src/aeat/application/modelo/tests/test_m145_communication_create.py src/aeat/application/modelo/tests/test_m145_communication_service_contract.py src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py --tb=short`
  - `uv run --no-sync pytest -q -n 0 src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py::test_secure_object_registry_names_m145_communication_record_namespace --tb=short`

## Notes

- The create path adds a central secure-storage namespace because the production namespace discovery gate requires every secure-object namespace to be registered.
- The broad namespace discovery test `test_every_discovered_production_secure_object_namespace_is_registered` currently fails on unrelated peer WIP: `aeat.outbound.aeat.auth.clave_permanente.diagnostics` is discovered but not registered. The M145 namespace-specific assertion passes.
- No bucket event type was added in this step. Communication-specific bucket events remain assigned to `P04.S21`.
