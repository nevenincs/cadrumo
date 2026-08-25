---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5dda6bf71d0dd337758ef58727d508ca0a5bf59f3910fe70f2c5d0747b7656b1'
step_id: 'S39'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace deadline recovery command transport with a canonical overview action

## Scope

- `src/cadrumo/domain/deadlines/_models.py`
- `src/cadrumo/domain/deadlines/_recargo.py`
- `src/cadrumo/domain/deadlines/tests/test_extemporaneidad.py`
- `src/cadrumo/domain/deadlines/tests/test_recargo.py`
- `src/cadrumo/application/overview`
- `src/cadrumo/entrypoints/cli/_overview_payloads.py`
- `src/cadrumo/entrypoints/cli/_overview_rendering.py`
- `src/cadrumo/entrypoints/cli/tests/test_overview_recovery_payload_parity.py`

## Description

- Delete `Recovery.next_command` so the deadline domain retains legal recovery facts only.
- Declare `operator.modelo.work.create` in the application overview with modelo, year, and period bindings.
- Resolve that declaration through the existing CLI action authority and reject retired raw command payloads.

## Outcome

Commit `7c104ceb6e` removed the raw deadline recovery command carrier and projects overdue pre-work recovery through the canonical `operator.modelo.work.create` action. The payload requires a resolved action and mutation-sensitive coverage rejects `next_command`.

VaultSpec RAG and independent review found no catalogue, verdict, evidence, or action-authority redeclaration. The focused owner proof passes 29 tests. The broader declared suite passes 40 tests and has five unrelated failures confined to the concurrently changing `_plazo.py` and registry deadline-window semantics.

## Notes

- S39 was closed only after the implementation commit was present, focused verification ran, and an independent Sol closure review returned PASS.
