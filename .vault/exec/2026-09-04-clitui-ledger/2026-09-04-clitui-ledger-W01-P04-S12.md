---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:bef8a880fb2c27b61f8bb0bf8bf4266e7e8399394c1d85a95a38e2710ad76d3f'
step_id: 'S12'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Review every row for explicit applicability, semantic owner, proof state, gap class, and next closure action

## Scope

- `.vault/reference/2026-09-04-clitui-ledger-reference.md`

## Changes

- `M` `dev/quality/clitui_ledger_capability_matrix.py`
- `M` `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P04-S12.md`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass (274 passed)
- `verify:` `uv run --no-sync ruff format --check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ruff check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync basedpyright dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass

## Notes

- The first independent review rejected S12 because 15 local input identities suppressed artifact obligations and the seven observed TUI route examples were incorrectly treated as exhaustive row routing.
- The corrected review makes those exact 15 inputs artifact-applicable and `UNPROVEN`; `ledger.import.source` is artifact-primary. The primary partition is 112 `AUTHORITY`, 546 `REGISTRY`, 34 `PRODUCT`, one `ARTIFACT`, and zero `COMPOSITION`.
- TUI disposition is now exhaustive: 680 applicable rows map to a reviewed route, 13 backend-helper-only rows map to none, and 679 component-only dispositions retain a `REACHABILITY` gap. The installed read-only Overview route proves only `ledger.workspace.read` reachability.
- G0 remains open for S13 reopening enforcement and S14 independent digest-bound acceptance.
