---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S37'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S37 - verify config auth extraction

Scope: `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run focused config auth surface tests.
- Run output-language parity tests for config auth commands.
- Run the CLI module size guard after the config root ratchet.
- Probe help output for every extracted auth verb.

## Outcome

Verification passed. `test_auth_round5_surface.py` reported 11 passing tests, `test_output_language_parity.py` reported 40 passing tests, and `test_cli_module_size.py` reported 2 passing tests. Help checks for providers, configure, status, test, login, and clear all exited 0 and exposed `--output-language`.

## Notes

The config root budget is ratcheted to the current extracted size of 2233 lines in the size guard.
