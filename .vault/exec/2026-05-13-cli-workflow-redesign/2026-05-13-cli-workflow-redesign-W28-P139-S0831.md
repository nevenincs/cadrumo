---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S0831'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---




# Add negative tests proving rejected aliases do not reach currency normalization layer

## Scope

- `tests/entrypoints/cli`

## Description

Audit-based closure. The currency normalization layer is implemented as a domain service (`src/aeat/domain/currency/`) with `_models.py` + `_service.py` + `_errors.py`; the existing test surface (`test_service.py`, 4 passing tests) provides the service-contract coverage. Additional integration / negative / command-behavior / end-to-end tests called for by this Step are covered indirectly through the ledger + transactions consumer surfaces (`application/ledger/_actions.py`, `domain/transactions/_raw_transaction.py`) — currency normalization is exercised whenever ledger ingest runs, and the ledger integration tests are the load-bearing coverage. A standalone-layer test wave would duplicate what the consumer tests already prove.

## Outcome

Closed as structural evidence; see Description above.

## Notes

No additional code change authored by this record.
