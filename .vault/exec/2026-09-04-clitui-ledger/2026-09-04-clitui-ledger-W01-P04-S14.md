---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:5858b19108722a8dbeacb4551ee7e1ee400ec607fd3e5273aebb82822321b430'
step_id: 'S14'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Record G0 closure only after an independent engineering review accepts the frozen matrix

## Scope

- `.vault/reference/2026-09-04-clitui-ledger-reference.md`

## Changes

- `M` `dev/quality/clitui_ledger_capability_matrix.py`
- `M` `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P04-S14.md`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py -k "canonical_matrix or g0 or acceptance_record_anchor or external_acceptance or gate_reopening_accepts_only"` -> `pass` (51 passed)
- `verify:` `vaultspec-core vault plan check clitui-ledger` -> `pass`

- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py -k human_matrix_contract_coordinate_matches_live_source_digest` -> `pass` (1 passed)

## Notes

- `vaultspec-core vault check all` retains one pre-existing unrelated schema error in `.vault/adr/2026-08-28-test-reconciliation-sweep-adr.md`; all other check families are clean or warning-only.
- `LOW` deferred: the missing external-anchor diagnostic currently names accepted G3 closure even when evaluating G0. The frozen matrix source remains unchanged so the two independent receipts and source-bound anchor stay valid; correct the diagnostic in the next gate-governance source revision and remint acceptance through the normal reopening lifecycle.
