---
step_id: S222
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P09.S222 — bare-except AST gate test

## Outcome

Created `src/aeat/test_no_bare_except.py` with a single real-behavior test:

- `test_no_bare_except_in_test_surface`: walks all `test_*.py` files under
  `src/aeat/` using `ast.parse`, inspects every `ast.Try` node's handlers,
  and fails with a precise file:lineno report if any bare `except:` or
  `except Exception: pass` pattern exists. No mocks, no subprocess, no skip.

Marked `pytest.mark.unit + pytest.mark.domain_core`. Ruff clean.

## Files touched

- `src/aeat/test_no_bare_except.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/test_no_bare_except.py -xvs` — 1 passed.
`vault plan step check S222` applied.
