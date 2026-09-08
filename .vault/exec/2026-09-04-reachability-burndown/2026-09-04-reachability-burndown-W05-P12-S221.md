---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:89b89abe1b770be306ac05970c5861302428a21138a4add67ebdf66088f39f2d'
step_id: 'S221'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the empty test-driven secure-object upgrader registry, its register/deregister and chain-projection APIs, the orphaned synthetic repository upgrade test, and synthetic chain tests; simplify the live row boundary to exact-current schema validation and direct decrypted-payload return while retaining future/older refusal ordering, current writes, inner-envelope version/classification checks, and real repository roundtrips.

## Scope

- `Secure-object schema-lineage owner and row codec`
- `orphaned/synthetic upgrade tests`
- `concrete version/refusal and decode-order tests`
- `exact reachability signal`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/adapters/persistence/storage/__init__.py`
- `M` `src/cadrumo/adapters/persistence/storage/schema_lineage.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/_secure_object_row_codec.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_object_decode_order.py`
- `D` `src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_schema_lineage.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_inner_envelope_vacuity_invariants.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_inner_envelope_version_check_shape.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S221.md`
- `verify:` `rg -n "register_secure_object_schema_upgrader|deregister_secure_object_schema_upgrader|upgrade_secure_object_payload|missing_upgrade_hops|SECURE_OBJECT_DURABILITY_FLOOR|SecureObjectSchemaUpgrader" src/cadrumo --glob '*.py'` -> `pass (no production or executable-test references; only detector fixture text was replaced)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/schema_lineage.py src/cadrumo/adapters/persistence/storage/sql/_secure_object_row_codec.py src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py src/cadrumo/adapters/persistence/storage/tests/test_inner_envelope_vacuity_invariants.py src/cadrumo/adapters/persistence/storage/tests/test_inner_envelope_version_check_shape.py src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_object_decode_order.py src/cadrumo/adapters/persistence/storage/__init__.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s221 src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py src/cadrumo/adapters/persistence/storage/tests/test_inner_envelope_vacuity_invariants.py src/cadrumo/adapters/persistence/storage/tests/test_inner_envelope_version_check_shape.py src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_object_decode_order.py src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part1.py src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part3.py` -> `pass (79 passed)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 61 unreachable modules, 308 exact unused symbols, 12 orphaned tests, 2029/2091 shipped modules reachable)`
