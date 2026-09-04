---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:365acb5dc998490bb036b1fd2dc24b6b0002f9bb8c489d9215bfbd651d7c7766'
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
- `verify:` `uv run --no-sync pytest -q dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass` (135 passed)
- `verify:` `uv run --no-sync pytest -q <nine S06 behavior files>` -> `environmental setup error` (86 passed; one M369 case refused before behavior with `KDF_RESOURCE_LIMIT`)
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py -k "exterior_period_calculate_review_export_e2e"` -> `pass` (4 passed; affected lane rerun serially)
- `verify:` `uv run --no-sync ruff format --check ... && uv run --no-sync ruff check ... && uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py && uv run --no-sync basedpyright ...` -> `pass`

## Notes

The shared-worktree formatter committed the reference-body change as `513ed0a123` before the Step Record and plan closure were ready. Shared automation then committed the Step Record and plan state as `87fb621848`; the generated feature index followed in `fcac0237d6`, and the full source-revision correction in `9428f7b7d0`. The split is retained rather than rewriting concurrent history.

The independent S06 reviews first required a committed byte-level projection contract and then identified selector defaults/nulls lost by the operational `selector_as_dict` view. The final remediation serializes the live validated selector model with every declared field/default/null retained, excluding only injected `source`, and proves live-boundary default/null mutation plus irrelevant input-order normalization. The canonical route digest is `sha256:20b2d2df5558b2a3fdbd1eab6e9f781a973e93c6211e211f8e679cf7b4782aca`; its 130-file source-set digest remains `sha256:194a9f26ddfbae6c5d7f265ffe58f50964fbe2fcd02a5670fa19845dead5cf6d`.

The second remediation's parallel nine-file behavior run was not an uninterrupted 87-pass run: 86 tests passed and one parametrized M369 case failed during profile-custody setup with `KDF_RESOURCE_LIMIT`, before the behavior under test ran. The complete affected four-case M369 exterior-period lane then passed serially. This environmental setup refusal is retained here rather than represented as a product pass.
