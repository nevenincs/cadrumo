---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-06'
modified: '2026-06-06'
step_id: 'S46'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
---

# `cross-period-filing-clean-state` `W05.P12.S46` exec - member-scoped filing identity

## Description

Added optional `member_nif` identity to `ModeloRecord`. Non-member records preserve their legacy filing-record id derivation, while member records include the member NIF in the derived id. Current-record uniqueness and `current_for` / `history_for` queries are now keyed by `(bucket_id, modelo, filing_year, period, member_nif)`.

## Outcome

Distinct current group member filings can coexist for the same source modelo/year/period, while duplicate current records for the same member are still rejected by the catalogue invariant.

## Verification

Command passed: `uv run --no-sync pytest src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q`.

Command passed: `uv run --no-sync ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/_protocols.py src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
