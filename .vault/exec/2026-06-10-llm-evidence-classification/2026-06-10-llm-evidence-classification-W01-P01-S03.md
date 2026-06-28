---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S03'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Add a real-behaviour test for evidence resolution from linked ids to decrypted evidence-input

## Scope

- `src/aeat/application/ledger/tests/test_evidence_input.py`

## Description

- Add real-behaviour tests: secure-storage byte round-trip, refusal of records without in-store bytes, and the persistence tripwire.

## Outcome

Commit `983143078`; expanded with nested/dict/pickle leak-vector regressions in `dbf92f608`. 20 tests green.

## Notes

Part of Wave W01; reviewed in audit `2026-06-10-llm-evidence-classification-audit` (gate PASS).
