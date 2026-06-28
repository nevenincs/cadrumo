---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S88'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S88 Core Application Error Registry Verification

Scope: verify core application error registry behavior and facade imports after decomposition.

## Description

- Verified core error registry tests after the application registry split.
- Verified compileall for `src/aeat/core/errors/registry`.
- Verified application registry entries are included in the aggregate registry tuple.
- Verified selected core boundary and output rendering tests that exercise public core error behavior.

## Outcome

The application registry shard split preserves the core errors facade and aggregate registry behavior.

## Notes

Passing checks: Ruff for application registry files; 34 core error tests; compileall for `src/aeat/core/errors/registry`; registry aggregate smoke check for 128 application entries; and 6 selected core boundary/output tests. The broader `src/aeat/core/tests` directory currently fails in unrelated external-constants and file-permissions path-fixture checks that look for missing `src/src/...` or test-local fixture paths; those failures are outside the error registry split.
