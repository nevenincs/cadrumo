---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:5f9f1b6ad3db70a78e426649aede6d8408fb6ede1a8ce6c5c1c9c8569f7d2c67'
step_id: 'S06'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Enumerate the seven binding families, every declared route, calculation consumer, filing consumer, and unresolved proof obligation

## Scope

- `src/cadrumo/domain/calculations/registry/bindings.py`

## Changes

- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `M` `dev/quality/clitui_ledger_capability_matrix.py`
- `M` `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P02-S06.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `verify:` `validated-authority structural census (7 families; 546 declarations; 35 family/revision sites; 510 registry-bound; 3 sidecar; 33 unresolved)` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_source_enrollment.py src/cadrumo/application/modelo/tests/test_source_boundary_and_enrollment.py src/cadrumo/application/modelo/tests/test_dormant_ledger_resolvers_fire_live.py src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py src/cadrumo/application/modelo/tests/test_unresolved_binding_diagnostics.py src/cadrumo/application/aggregation/tests/test_impatriado_income_ledger.py src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py src/cadrumo/application/aggregation/tests/test_renta_income_aggregation.py` -> `pass` (87 passed)
- `verify:` `uv run --no-sync pytest -q dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass` (131 passed)

## Notes

The shared-worktree formatter committed the reference-body change as `513ed0a123` before the Step Record and plan closure were ready. Shared automation then committed the Step Record and plan state as `87fb621848`; the generated feature index followed in `fcac0237d6`, and the full source-revision correction in `9428f7b7d0`. The split is retained rather than rewriting concurrent history.

The independent S06 review reopened the step because the first route digest lacked a committed byte-level projection contract. The remediation adds the strict live-authority-derived v1 projection and mutation detector; the canonical route digest is `sha256:247b82a244e2a8c9a6ca476cc6aa46a3e15b7357f2aa206f4148fee18175f9ac`, and its 130-file source-set digest is `sha256:194a9f26ddfbae6c5d7f265ffe58f50964fbe2fcd02a5670fa19845dead5cf6d`.
