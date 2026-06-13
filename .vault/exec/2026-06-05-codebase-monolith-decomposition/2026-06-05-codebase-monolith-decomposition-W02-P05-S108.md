---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S108'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S108 - split modelo registry surface tests

Scope: `src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`.

## Description

- Move the selected registry/discovery and key-validation tests into `test_modelo_registry_surface.py`.
- Keep the test logic and real CLI invocations intact.
- Update the stale calculation-boundary source assertion to inspect `calculate_modelo_work_revision`, where the current application boundary now lives.

## Outcome

`test_modelo.py` is smaller and the extracted registry/discovery module owns the moved surface and parser contracts. The updated boundary test still proves the work calculation path enters bucket-backed aggregation.

## Notes

No fakes, mocks, skips, or xfails were introduced.
