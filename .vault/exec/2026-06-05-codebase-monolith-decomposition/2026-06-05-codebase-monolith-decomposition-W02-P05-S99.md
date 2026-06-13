---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S99'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S99 - verify config bucket history extraction

Scope: `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run ruff over the config root, extracted repair/bucket modules, policy scanner, and size guard.
- Run bucket-history parser tests, the profile lifecycle bucket-event history assertion, the bucket verb roster guard, policy coverage, and CLI module-size guard.
- Ratchet `_config/__init__.py` to its current line count after the bucket-history extraction.

## Outcome

Focused bucket-history verification passed. Ruff reported no issues, parser and lifecycle/roster checks reported 47 passing tests, and the CLI module-size guard pins the config root at the new smaller line budget.

## Notes

The broader combined config gate also includes the long repair privacy contract before this tranche is committed. S100 records the fresh-process output-language parity rerun that passed with 40 tests.
