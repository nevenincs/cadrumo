---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S12'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# assert the current guard_unsupported_work_modelo hard refusal at work create still fires for no-engine and unsupported stubs (vaultspec-code-reviewer)

## Scope

- `src/aeat/application/modelo/_work_create_policy.py`
- `src/aeat/entrypoints/cli/tests/test_modelo_unsupported_work_refusal.py`
- `src/aeat/entrypoints/cli/tests/test_root_fallback_write_guard.py`

## Description

- Reconcile the stale `_guard_stub_modelo` wording against the current `guard_unsupported_work_modelo` policy.
- Ground the row with `uvx vaultspec-rag search "guard_stub_modelo work create no engine stubs authorization advisory banner test" --type code --limit 12`.
- Confirm unsupported/no-engine work-create refusals are enforced through `guard_unsupported_work_modelo` and the root-fallback leaf-refusal path.
- Update the plan row from the old `_guard_stub_modelo` symbol and stale test path to the current policy and tests.
- Run the focused refusal tests instead of the entire file, because one unrelated legal-source catalogue assertion in the broad file currently fails on `boe-modelo-151-form`.

## Outcome

- `uv run --no-sync pytest -q -n 0 -m integration src\aeat\entrypoints\cli\tests\test_modelo_unsupported_work_refusal.py::test_m210_engine_live_flag_only_bypasses_m210_guard src\aeat\entrypoints\cli\tests\test_root_fallback_write_guard.py::test_stub_only_modelo_work_create_reaches_leaf_refusal_on_root_fallback_database`: 2 passed.
- `uv run --no-sync pytest -q -n 0 -m integration src\aeat\entrypoints\cli\tests\test_modelo_unsupported_work_refusal.py::test_work_create_unsupported_modelo_refuses_with_legal_authority src\aeat\entrypoints\cli\tests\test_modelo_unsupported_work_refusal.py::test_m210_guard_refuses_when_engine_live_flag_is_unset`: 9 passed.
- No production source changed in this reconciliation pass.

## Notes

- Broad `test_modelo_unsupported_work_refusal.py` currently has an unrelated failure in `test_registry_entries_for_unsupported_local_work_are_legally_grounded`: `boe-modelo-151-form` is not present in `catalogues.sources`. That is not the S12 guard/refusal behavior.
