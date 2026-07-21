---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S18'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Update the transaction repository protocol to describe summary diagnostics

## Scope

- `src/aeat/domain/transactions/_protocols.py`

## Description

- Attempt semantic search for the partition protocol and summary diagnostics contract.
- Read the current repository protocol, the new domain summary model, and the research contract note before editing.
- Update `partition_by_date_range` protocol documentation to allow either migration stubs or compact count/date-span summaries.
- Preserve the no-silent-drop requirement and the restriction to plaintext date-index facts.
- Run domain ruff checks and a direct `LedgerDatePartition` construction check.
- Audit the change and record that no open findings remain.

## Outcome

`TransactionCatalogueRepositoryProtocol.partition_by_date_range` now describes the summary diagnostics contract: implementations must still return the same in-window transaction set and represent every out-of-window transaction, but may use the ADR-authorized count/date-span summary instead of row-level stubs during the migration.

## Notes

The RAG attempt hit the local index lock. Direct reads supplied the grounding. Ruff passed for the protocol, domain model, and facade; direct partition construction with no summary also passed.
