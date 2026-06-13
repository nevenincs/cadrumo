---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S39'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P08.S39 Ledger Period Parser Reconciliation

Scope: reconcile the already-landed strict AEAT-token ledger period parser with the amended D4 decision.

## Description

- Verified ledger `--period` parsing accepts AEAT tokens with `--year`.
- Verified calendar shapes and year-qualified hybrids are refused.
- Verified the plan row now matches the ADR amendment that superseded the older conversion-layer wording.

## Outcome

S39 is closed. Ledger period parsing uses the canonical AEAT token plus year shape and validates through the registry period union.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`.
