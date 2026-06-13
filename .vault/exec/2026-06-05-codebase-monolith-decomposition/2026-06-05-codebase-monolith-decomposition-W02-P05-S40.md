---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S40'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S40 - verify live expedientes extraction

Scope: `src/aeat/entrypoints/cli/tests/test_live* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ratchet the live root size budget to the extracted `_app_live.py` size.
- Run focused live subgroup behavior tests.
- Run expedientes capture-all CLI help coverage.
- Probe help output for every expedientes command path.
- Run the global CLI module and command size guard.

## Outcome

Verification passed after the adjacent modelo reconcile registrar was flattened under `S41-S43`. `test_live_read_subgroups.py` reported 25 passing tests, the expedientes capture-all help test passed, expedientes help checks exited 0, and `test_cli_module_size.py` reported 2 passing tests.

## Notes

The live root budget is ratcheted to 1177 lines. The initial size-guard run exposed an unrelated oversized `register_reconcile_commands` function, which was handled as the next modelo closure slice rather than hidden by a budget exception.
