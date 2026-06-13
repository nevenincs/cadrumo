---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S08'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P02.S08 - decomposition guard verification

Scope: verify decomposition guards fail on newly introduced private backend bypasses.

## Description

- Add guard logic that computes private backend imports from the legacy root AST.
- Add guard logic that counts direct registry authority reads and direct registry service construction.
- Run the architecture lane to prove the current baseline passes.
- Confirm the assertions compare current code against fixed budgets, so new bypasses become test failures.

## Outcome

The architecture guard suite now has five tests. The two new legacy-root guards make private backend imports and registry authority reads explicit frozen debt rather than reviewer-only knowledge.

## Notes

Verification: `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py -q` passed.
