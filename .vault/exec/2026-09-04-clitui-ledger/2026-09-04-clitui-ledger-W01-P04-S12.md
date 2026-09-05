---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:f9176fb955e91f0114949faf127a780f22d37779c68d4a4fc2eb02e9ca76cf2e'
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
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass (277 passed)
- `verify:` `uv run --no-sync ruff format --check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ruff check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync basedpyright dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass

## Notes

- The first independent review rejected S12 because 15 local input identities suppressed artifact obligations and the seven observed TUI route examples were incorrectly treated as exhaustive row routing.
- The corrected review makes those exact 15 inputs artifact-applicable and `UNPROVEN`; `ledger.import.source` is artifact-primary. The primary partition is 112 `AUTHORITY`, 546 `REGISTRY`, 34 `PRODUCT`, one `ARTIFACT`, and zero `COMPOSITION`.
- TUI disposition is now exhaustive: 680 applicable rows map to a reviewed route, 13 backend-helper-only rows map to none, and 679 component-only dispositions retain a `REACHABILITY` gap. The installed read-only Overview route proves only `ledger.workspace.read` reachability.
- A second independent review found that `ledger.transaction.invoice_link` belonged to Reconciliation rather than Entries and that the 15-input list still suppressed live `CommandSpec` transport facts. The route is corrected, every supported-surface selection must now join to its selected row's route, and artifact-input authority is derived from all live `LOCAL_IN` file/directory parameters plus reviewed existing/planned additions.
- The final artifact-input census is 29 CLI-derived rows, 30 current rows after `ledger.import.source`, and 31 including planned `ledger.evidence.replace`; 39 rows are artifact-applicable after output/query products are included. Metadata, semantic-selection, route, and fully digest-reminted serialized mutations fail closed.
- G0 remains open for S13 reopening enforcement and S14 independent digest-bound acceptance.
