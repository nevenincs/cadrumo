---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S46'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S46 - verify google config closure extraction

Scope: `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Remove the Google root from the legacy size-budget table because extracted `_google.py` is now below the default 800-line limit.
- Run focused Google sync calc, sync push, and error-localisation tests.
- Run the global CLI module and command size guard.
- Run lint checks for touched Google files.

## Outcome

Verification passed. Google-focused tests plus the CLI size guard reported 15 passing tests, and lint checks passed for the touched Google files.

## Notes

The Google root now relies on the default 800-line budget at 734 lines. The size guard file also carries prior uncommitted residual CLI root ratchets from the shared worktree; those match the already closed monolith plan records for earlier CLI closure slices.
