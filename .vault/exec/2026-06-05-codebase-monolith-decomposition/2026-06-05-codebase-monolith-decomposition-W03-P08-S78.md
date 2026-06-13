---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S78'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S78 Google Calc Sheets Apply Verification

Scope: verify Google calc sheets apply behavior and facade imports after decomposition.

## Description

- Run `uv run --no-sync pytest src/aeat/adapters/outbound/google/tests -q --tb=short`.
- Run `uv run --no-sync pytest src/aeat/entrypoints/cli/_config/tests/test_google_sync_calc_pull_flag.py src/aeat/entrypoints/cli/_config/tests/test_google_sync_push.py src/aeat/entrypoints/cli/_config/tests/test_google_error_localisation.py -q --tb=short -m integration`.
- Run `uv run --no-sync ruff check` over the touched Google adapter and focused config surfaces.
- Run an import smoke for `OAuthClient`, `OAuthToken`, and `REQUIRED_SCOPES` from the top-level Google facade.
- Search application, entrypoint, and domain code for direct imports into the new private value-write module.

## Outcome

Google adapter tests passed with 152 selected tests and 3 deselected tests. Focused config Google integration tests passed with 13 tests. Ruff passed for the touched Google and config-test surface. The top-level Google facade import smoke succeeded. The private-module consumer search returned no application, entrypoint, or domain imports.

## Notes

The old private `_calc_sheets_apply.py` helper names remain importable for same-package adapter tests as compatibility re-exports.
