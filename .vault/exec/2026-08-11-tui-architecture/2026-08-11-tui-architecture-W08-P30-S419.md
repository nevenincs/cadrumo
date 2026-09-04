---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:6503a424c2bb341a2d7ec325a210129a48e2b78e8db6c2407dd6f93430cbe143'
step_id: 'S419'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Catch the capture-coherence refusal on the Home refresh path. INDEPENDENT REVIEW 2026-09-04: the guard raises RuntimeError when a concurrent write changes the profile mid-capture, which is correct, but that exception propagates through the Home refresh door and _show_home catches only AccountSessionExpiredError -- so a sibling aeat CLI process writing while the TUI returns to Home terminates the session with a traceback instead of refusing the refresh. The identical failure is handled correctly one method away in _rebuild_workbench_search, so this is an asymmetry rather than a policy.

## Scope

- `src/cadrumo/entrypoints/tui/app.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/app.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_app.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/tui/tests/test_app.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py src/cadrumo/entrypoints/tui/tests/test_workbench_security.py` -> `pass`

## Notes

The Home refresh path caught only AccountSessionExpiredError, so the capture-coherence
refusal added earlier in this campaign would have ended the session with a traceback over a
concurrent write -- in a worktree that demonstrably has concurrent writers. A refused
refresh is now an outcome: the operator keeps the Home they are looking at and the root
publishes a sanitized code.

Two gates. The second exists because the obvious fix is wrong in the other direction:
widening the expiry branch to catch everything would discard a live profile-bound root over
a concurrent write, so it asserts a refusal is NOT reported as an expiry.

Teeth proven by deleting the handler: both fail.
