---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S104'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S104 Ledger Residual Slice Discovery

Scope: `src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/entrypoints/cli/tests`.

## Description

- Run semantic RAG discovery against `_ledger.py` for remaining command groups.
- Run exact symbol and test discovery for ledger providers, categories, check, preflight, history, export, list, view, status, track, and review.
- Inspect the remaining command-region dependencies and existing extracted ledger modules.

## Outcome

Selected the ledger read/discovery/reporting command group for extraction. The group includes `providers`, `categories`, `check`, `preflight`, `history`, `export`, `list`, `view`, `status`, `track`, and `review`, and excludes mutating `allocate` and `link` so the extracted module has a clear query/reporting responsibility.

## Notes

The selected slice is large enough to reduce `_ledger.py` below the production-module monolith threshold while avoiding the shared transaction update path.
