---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S95'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S95 - extract config repair maintenance commands

Scope: `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_repair_cli.py src/aeat/entrypoints/cli/tests/test_repair_policy_coverage.py`.

## Description

- Move residual `config repair` maintenance verbs into `_config/_repair_cli.py`.
- Keep the command behavior as transport-only CLI registration over existing diagnostics, workflow, and secure-storage application services.
- Mount the extracted registrar from `_config/__init__.py` without changing the public `config repair ...` command paths.
- Extend the repair-policy source scanner so it follows extracted registrar modules for `repair`, `ledger import`, and `modelo` recovery/audit verbs.

## Outcome

The config root now delegates repair maintenance commands to a focused registrar while preserving the existing command topology. The repair-policy catalog gate continues to compare canonical policy rows against source-discovered CLI surfaces instead of hard-coded test expectations.

## Notes

`config repair profile` remains owned by the existing `_repair_profile.py` registrar. The maintenance extraction covers `logs`, `quarantine`, `reset-state`, `integrity objects`, `integrity registry`, and `connectivity`.
