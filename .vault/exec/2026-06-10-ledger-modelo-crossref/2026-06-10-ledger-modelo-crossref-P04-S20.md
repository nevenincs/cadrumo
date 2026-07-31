---
tags: ['#exec', '#ledger-modelo-crossref']
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:cfa74db1aefa06e31d2323878759b071ddd2e7cb060676fcf6abe3639e1ba33b'
step_id: 'S20'
related:
  - '[[2026-06-10-ledger-modelo-crossref-plan]]'
  - '[[2026-06-10-ledger-modelo-crossref-adr]]'
  - '[[2026-06-10-ledger-modelo-crossref-research]]'
---

# ledger-modelo-crossref P04.S20

Read and CLI phase record for `P04.S20`.

## Description

- Verified `aeat app ledger participation <transaction-id>` is registered and emits `LedgerTransactionParticipationPayload`.
- Confirmed `--include-borradores` is declared as a reserved no-op flag.

## Outcome

Step closed by CLI surface tests.

## Notes

Borrador participation remains intentionally deferred to a sibling/future scope.
