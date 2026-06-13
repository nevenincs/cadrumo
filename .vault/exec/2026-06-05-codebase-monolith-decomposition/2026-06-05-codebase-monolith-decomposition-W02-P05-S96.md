---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S96'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S96 - verify config repair command extraction

Scope: `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_repair_*.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run ruff over the config root, repair registrars, policy-coverage test, and module-size guard.
- Run repair reset-state, bootstrap exemption, policy coverage, privacy contract, workflow surface, and CLI module-size tests.
- Ratchet the config root legacy line budget after the maintenance extraction.

## Outcome

Verification passed. Ruff reported no issues, and the focused repair extraction test gate reported 28 passing tests.

## Notes

The repair privacy contract is integration-heavy. The full focused repair gate completed in 97.72 seconds.
