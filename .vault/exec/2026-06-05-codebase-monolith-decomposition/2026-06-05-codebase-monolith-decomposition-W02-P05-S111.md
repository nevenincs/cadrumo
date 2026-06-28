---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S111'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S111 - verify modelo audit extraction

Scope: `src/aeat/entrypoints/cli/tests/test_audit_verbs.py`, `src/aeat/entrypoints/cli/tests/test_root_grammar_invariants.py`, `src/aeat/entrypoints/cli/tests/test_repair_policy_coverage.py`, `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Run ruff over the modelo root, audit/reconcile registrars, audit tests, root grammar tests, repair-policy discovery, and the CLI size guard.
- Run audit verb behavior tests, root grammar invariants, repair-policy coverage, and the CLI module-size guard.

## Outcome

Verification passed. Ruff reported no findings, and pytest reported 23 passing tests for the audit extraction gate.

## Notes

The repair-policy AST scanner now includes the audit registrar so `app modelo audit export` remains covered by the canonical repair/recovery policy catalog.
