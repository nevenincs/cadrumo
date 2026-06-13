---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S49'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S49 - verify residual ledger root extraction

Scope: `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run lint against `_ledger.py`, the extracted ledger registrar modules, and the CLI size guard.
- Run focused ledger command-surface, provider, doclink, and size-guard tests.
- Ratchet `_ledger.py` to the extracted size in the CLI module-size guard.
- Update the ledger verb-spine roster to include the already-mounted and behavior-tested `doclink` and `providers` commands.

## Outcome

Focused verification passed: ruff reported no issues, and the targeted ledger command-surface/provider/doclink/size tests reported 15 passing tests. `_ledger.py` is now budgeted at 1946 lines after extracting import, lifecycle, and rule command groups.

## Notes

A broader ledger-focused run also surfaced failures outside this closure proof: storage route mismatch failures in validation-path tests and missing fixture-path failures in FX import tests. Those failures were not hidden; they remain outside this commit's passing gate and need a separate storage/fixture cleanup slice.
