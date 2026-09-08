---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e9d8b1b84a5fbd65f075d19f156421e429119247f5f781d535d2daa9c4cde5f0'
step_id: 'S133'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Retire the generated size-budget baseline, thresholds, regeneration path, and shipped test helper because line-count debt snapshots are development metastate rather than a semantic quality authority

## Scope

- `size-budget ADR`
- `audit implementation and tests`
- `shipped test facade`
- `CI and just recipes`
- `and stale documentation`

## Changes

- `M` `.vault/adr/2026-07-09-size-budget-refactor-adr.md`
- `M` `.github/workflows/ci.yml`
- `D` `dev/audit/size_budget.py`
- `D` `dev/audit/size_budget_baseline.json`
- `D` `dev/audit/tests/test_size_budget_baseline.py`
- `D` `dev/audit/tests/test_size_budget_dev_corpus.py`
- `M` `dev/audit/advisory.py`
- `M` `dev/quality/default_lane_visibility.py`
- `M` `dev/quality/tests/test_default_lane_visibility.py`
- `M` `dev/tests/test_text_writer_newline_pinning.py`
- `M` `justfile`
- `M` `src/cadrumo/tests/__init__.py`
- `D` `src/cadrumo/tests/size_budget.py`
- `verify:` `uv run ruff check <S133 Python paths>` -> `pass`
- `verify:` `uv run pytest -q -n0 dev/quality/tests/test_default_lane_visibility.py` -> `pass`
- `verify:` `import cadrumo.tests and dev.audit.advisory` -> `pass`
- `verify:` `rg exact retired size-budget mechanism symbols and commands` -> `pass`
