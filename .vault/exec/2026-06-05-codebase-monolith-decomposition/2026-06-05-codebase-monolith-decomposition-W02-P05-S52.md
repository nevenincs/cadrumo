---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S52'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S52 - verify residual config auth extraction

Scope: `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run ruff against the config facade, extracted auth module, and CLI size guard.
- Run auth round-five, output-language parity, workflow auth surface, and CLI module-size tests.
- Keep `_config/__init__.py` within its current ratcheted budget after extraction.

## Outcome

Verification passed. Ruff reported no issues, and the auth/output-language/workflow/size test gate reported 54 passing tests.

## Notes

The config root remains above the default 800-line budget and is still governed by the shrinking legacy budget until the remaining profile, repair, bucket, reset, and status surfaces are decomposed.
