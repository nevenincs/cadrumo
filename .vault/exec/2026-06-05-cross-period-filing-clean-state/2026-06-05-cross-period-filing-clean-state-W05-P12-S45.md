---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-06'
modified: '2026-06-06'
step_id: 'S45'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
---

# `cross-period-filing-clean-state` `W05.P12.S45` exec - member-scoped filing history contract

## Description

Exposed the member-scoped filing-history query contract on the domain protocol surface. Loaded filing-record catalogues now document `current_for` and `history_for` with an optional `member_nif` axis so application services can query group member filings without traversing private modules.

## Outcome

The protocol surface now reflects the widened filing-record catalogue behavior required by group fan-in clean-state proof.

## Verification

Command passed: `uv run --no-sync ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/_protocols.py src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
