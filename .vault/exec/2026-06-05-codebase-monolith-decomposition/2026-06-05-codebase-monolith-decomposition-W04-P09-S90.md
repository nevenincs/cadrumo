---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:632a86a0a16b5a2bef677eecd5183f3b9b4f10223954eb960e4dbe9fa83bd44b'
step_id: 'S90'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S90 Core Adapter Error Registry Verification

Scope: verify core adapter error registry behavior and facade imports after decomposition.

## Description

- Verified core error registry tests after the adapter registry split.
- Verified compileall for `src/aeat/core/errors/registry`.
- Verified adapter registry entries are included in the aggregate registry tuple.
- Verified the repository hard size-budget gate.

## Outcome

The adapter registry shard split preserves core errors facade behavior and keeps registry files within hard size limits.

## Notes

Passing checks: Ruff for adapter registry files; 34 core error tests; compileall for `src/aeat/core/errors/registry`; registry aggregate smoke check for 117 adapter entries; and `src/aeat/tests/test_codebase_size_budgets.py`.
