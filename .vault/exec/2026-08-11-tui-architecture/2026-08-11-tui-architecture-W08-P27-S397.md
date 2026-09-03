---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:f2c2fe83aad79f3c48d5b5592422992c721fb7e99c9224e5751ac148097b1d57'
step_id: 'S397'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define a safe immutable AEAT Sync workspace projection that joins overview, census, filed-declaration, notification, evidence-comparison, and reconciliation facts while excluding protected taxpayer values and preserving source availability, freshness, contradiction, and supported-action axes

## Scope

- `src/cadrumo/application/aeat_sync/workspace.py and focused application tests`

## Changes

- `M` `src/cadrumo/application/aeat_sync/__init__.py`
- `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `A` `src/cadrumo/application/aeat_sync/tests/__init__.py`
- `M` `src/cadrumo/application/aeat_sync/tests/test_workspace.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `M` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s397-review-audit.md`
- `A` `.vault/exec/2026-08-11-tui-architecture/2026-08-11-tui-architecture-W08-P27-S397.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/aeat_sync/tests/test_workspace.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/aeat_sync/__init__.py src/cadrumo/application/aeat_sync/workspace.py src/cadrumo/application/aeat_sync/tests/test_workspace.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/aeat_sync/__init__.py src/cadrumo/application/aeat_sync/workspace.py src/cadrumo/application/aeat_sync/tests/test_workspace.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright src/cadrumo/application/aeat_sync/__init__.py src/cadrumo/application/aeat_sync/workspace.py src/cadrumo/application/aeat_sync/tests/test_workspace.py` -> `pass`
- `verify:` `npx --yes jscpd@4.2.0 src/cadrumo/application/aeat_sync/__init__.py src/cadrumo/application/aeat_sync/workspace.py src/cadrumo/application/aeat_sync/tests/test_workspace.py --format python --min-lines 6 --min-tokens 80 --max-size 250kb --reporters console --noTips` -> `pass`
- `fix:` promoted the shared capability-provenance base to the public immutable
  row contract and applied it to all six concrete row families, ensuring real
  projected instances retain and safely serialize admitted action and operation
  references.
- `verify:` regression-focused pytest -> `12 passed`; Ruff -> `pass`; ty ->
  `pass`; basedpyright -> `0 errors, 0 warnings`; targeted jscpd -> `0 clones`.
- `review:` independent vaultspec code review -> `APPROVE` with no admission,
  source-closure, or protected-data regression.
