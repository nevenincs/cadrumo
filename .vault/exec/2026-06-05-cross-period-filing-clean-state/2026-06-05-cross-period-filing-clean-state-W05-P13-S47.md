---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-06'
modified: '2026-06-06'
step_id: 'S47'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
---

# `cross-period-filing-clean-state` `W05.P13.S47` exec - member-scoped group proof wiring

## Description

Changed clean-state evaluation for `per_grupo_member` dependencies so group fan-in verifies each expected member's current filing record independently. Each member filing must have AEAT acceptance, external justificante-grade evidence, a presented calculation revision, and values reconciled to the member-scoped observation.

## Outcome

Modelo 353 and future group aggregators no longer satisfy filing-grade proof from one unscoped source filing or from member observations alone. The proof records member filing record ids and member calculation revision ids when member evidence is clean.

## Verification

Command passed: `uv run --no-sync pytest src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` with 22 tests passing.

Command passed: `uv run --no-sync ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/_protocols.py src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
