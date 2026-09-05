---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:8f5efe5e9974995ab63b34a5d79ce91bd1479fa2aa9936f2af946843aebcdef0'
step_id: 'S11'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Mark every TUI-applicable union and matrix row held until G3, retain component-only versus installed distinctions, and fail closed on hold drift, additions, or an unauthorized lift

## Scope

- `dev/quality/clitui_ledger_capability_matrix.py`
- `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `.vault/reference/2026-09-04-clitui-ledger-reference.md`

## Changes

- `M` `dev/quality/clitui_ledger_capability_matrix.py`
- `M` `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P03-S11.md`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass (222 passed)
- `verify:` `uv run --no-sync ruff format --check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ruff check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync basedpyright dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-09-04-clitui-ledger-plan.md --json` -> pass
- `verify:` `uv run --no-sync vaultspec-core vault feature index --feature clitui-ledger --json` -> pass
- `verify:` `uv run --no-sync vaultspec-core vault check all --feature clitui-ledger --no-hints` -> pass

## Notes

S11 was reopened after the mandatory review found that an inactive hold could close individual G4 prematurely and made ordered G4 impossible after an authorized lift. The remediation adds a typed, ordered G0--G3 accepted-closure receipt chain bound to the current denominator, matrix closure basis, and independent acceptance subject. G4 now requires a current G3 receipt, and ordered evaluation preserves a valid historical G0 closure only across the authorized hold transition while current matrix, receipt, denominator, or observed-census drift relocks it. The row partition remains 680 held TUI-applicable rows and 13 unheld TUI-not-applicable rows.

- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py -k 'g4 or ordered_evaluation or active_pre_g3 or matrix_drift or denominator_and_observed or receipt_serialization'` -> pass (22 passed)
- `verify:` `uv run --no-sync ruff format --check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ruff check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync basedpyright dev/quality/clitui_ledger_capability_matrix.py` -> pass
