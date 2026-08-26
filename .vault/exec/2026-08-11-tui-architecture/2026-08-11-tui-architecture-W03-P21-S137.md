---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2a60847909813feae9d577dc5dc6c5ffbcac732eebdeb6f7d8ec741e508a5c8b'
step_id: 'S137'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Expose the edit facade and prove schema, parsing, preflight, scalar and row intent, guarded compare-and-swap, duplicate-result, rollback, compatibility refusal, persistence round-trip, non-retention, and redeclaration behavior while leaving operation-enrollment capability UNMEASURED until its C3 receipt exists

## Scope

- `src/cadrumo/application/modelo/__init__.py and src/cadrumo/application/modelo/tests/test_edit_contract.py`

## Changes

- `A` `src/cadrumo/application/modelo/_edit_facade.py`
- `A` `src/cadrumo/application/modelo/tests/test_edit_contract.py`
- `M` `src/cadrumo/application/modelo/_edit_services.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_services.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_execution.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py -q -n 0 -m "integration or unit"` -> `pass` (41 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_modelo_210_agrupacion_renta_e2e.py -q -n 0` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_edit_facade.py src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_edit_facade.py src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py` -> `pass`

## Notes

The Step's own scope names `__init__.py`, but `application/modelo/__init__.py`
is the deliberately inert package namespace (`Consumers import each contract
from its direct defining module`) per this campaign's facade rule (a narrow
public defining module, never `__init__.py`, stays inert). The facade lands
as a new module, `_edit_facade.py`, defining the one genuinely new piece of
logic this Step calls for -- the mutation-capability projection -- rather
than re-exporting S132-S136 symbols, which the architecture rules forbid as
much as touching `__init__.py` would.

`project_modelo_edit_mutation_capability` always projects `UNMEASURED` for a
resolvable target (never a fabricated `AVAILABLE`) and an empty row set for
an unresolvable one, per D1/D5's "mutation capability is unmeasured" until
the C3 financial-operand receipt is green.

Also closed a real gap found while building this Step's compatibility-refusal
proof: `admit_modelo_edit` never actually validated the compatibility tuple
against anything, so `unsupported_edit_compatibility` (D1) had no code path.
Added `modelo_edit_request_schema_identity` /
`modelo_edit_result_schema_identity` (this consumer's own current schema
fingerprints, computed directly rather than through
`OperationSchemaIdentityV1.from_model`, which enforces the unrelated
operations subsystem's own model-graph contract) and a real
`ModeloEditCompatibilityRefusalV1` path in admission. All S133/S135/S136 test
fixtures constructing a compatibility tuple were updated to use the real
identities instead of a placeholder digest, since the new check would
otherwise refuse every one of them.
