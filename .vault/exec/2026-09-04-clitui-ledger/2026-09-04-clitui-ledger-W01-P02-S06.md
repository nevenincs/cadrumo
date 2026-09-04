---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:68592868e9ac1b678b8e4475d88e78e29c1311a9e10c98b5f11773f0bc4639d5'
step_id: 'S06'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Enumerate the seven binding families, every declared route, calculation consumer, filing consumer, and unresolved proof obligation

## Scope

- `src/cadrumo/domain/calculations/registry/bindings.py`

## Changes

- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P02-S06.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `verify:` `validated-authority structural census (7 families; 546 declarations; 35 family/revision sites; 510 registry-bound; 3 sidecar; 33 unresolved)` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_source_enrollment.py src/cadrumo/application/modelo/tests/test_source_boundary_and_enrollment.py src/cadrumo/application/modelo/tests/test_dormant_ledger_resolvers_fire_live.py src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py src/cadrumo/application/modelo/tests/test_unresolved_binding_diagnostics.py src/cadrumo/application/aggregation/tests/test_impatriado_income_ledger.py src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py src/cadrumo/application/aggregation/tests/test_renta_income_aggregation.py` -> `pass` (87 passed)

## Notes

The shared-worktree formatter committed the reference-body change as `513ed0a123` before the Step Record and plan closure were ready. The scoped closure commit therefore contains the Step Record, plan state, and generated feature index; the source publication remains traceable to that immediately preceding commit.
