---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-06'
modified: '2026-06-06'
step_id: 'S48'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
---

# `cross-period-filing-clean-state` `W05.P13.S48` exec - member-scoped workflow coverage

## Description

Validated the Modelo workflow gate after member-scoped filing history became mandatory for group fan-in clean-state proof. The profile-derived Modelo 353 roster path now reaches filing enforcement and no longer reports `missing_expected_group_member_roster` when the profile contains the required 322 member roster.

## Outcome

The workflow refusal now correctly classifies incomplete group member coverage and missing member filing state through the real `file_modelo_revision` path.

## Verification

Command passed: `uv run --no-sync pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py -q` with 12 tests passing.

Command passed: `uv run --no-sync ruff check src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/_verification_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/_filing_actions.py`.
