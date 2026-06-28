---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S32
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W01.P02 — ledger query verbs

## Outcome

Added 5 query-verb `OutputSchema` subclasses to `_ledger_payloads.py`: `LedgerListResult`, `LedgerViewResult`, `LedgerStatusResult`, `LedgerHistoryResult`, `LedgerCategoriesResult`. Migrated their bare `_emit` sites in `_ledger.py` to `_emit_envelope`. `LedgerViewResult` uses `model_dump(mode="json")` on the `LedgerTransactionResultPayload` source to satisfy strict list/tuple typing.

## Files changed

- `src/aeat/entrypoints/cli/_ledger_payloads.py` — 5 query-verb schemas added
- `src/aeat/entrypoints/cli/_ledger.py` — 5 bare emit sites migrated

## Gate

109 ledger CLI tests + conformance gate passed.
