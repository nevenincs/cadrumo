---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:21f69f91c793b9adbade78d164894103eca52121a3122d6221d22e9f5a167da5'
step_id: 'S260'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only frontend capability detector while retaining the live shared no-console error probe used by the line frontend; remove its dedicated tests and replace stale detector-teeth fixture wording with identity-independent local symbols, run focused flow and prompter gates, remeasure exact reachability, update cadence, and write the Step Record.

## Scope

- `application flow capability helper and tests`
- `prompter singularity detector fixture`
- `focused gates`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/flows/capability.py`
- `D` `src/cadrumo/application/flows/tests/test_capability.py`
- `M` `src/cadrumo/tests/test_wizard_prompter_singularity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/flows/capability.py src/cadrumo/tests/test_wizard_prompter_singularity.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/flows/tests/test_line_frontend.py src/cadrumo/tests/test_wizard_prompter_singularity.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The production classifier had no product consumer, so its dedicated tests were not material. A proposed replacement AST-string fixture was rejected and the existing negative source-string test was deleted instead. The live line frontend and repository detector remain green at 27 focused tests. Exact unused symbols improved from 287 to 285; 31 unreachable modules remain.
