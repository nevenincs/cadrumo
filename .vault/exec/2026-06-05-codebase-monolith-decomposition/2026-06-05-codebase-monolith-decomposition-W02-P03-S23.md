---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S23'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S23 - residual ledger ratios selection

Scope: `src/aeat/entrypoints/cli/_ledger.py` and ledger CLI tests.

## Description

- Checked `vaultspec-rag` service health before semantic discovery.
- Ran exact discovery over remaining ledger command groups and related tests.
- Ran semantic discovery for ledger ratios command extraction.
- Selected `app ledger ratios` because it is a coherent sub-app with existing integration coverage and a sizeable helper/command block.

## Outcome

Selection completed. RAG ranked `ratios_validate`, `ratios_eligible`, `ratios_unset`, and `ratios_list` as coherent extraction candidates.

## Notes

The source-jurisdiction and censo business-pct helpers stayed in `_ledger.py` because `ledger_add` still uses them; relocating those should be a separate backend-boundary step.
