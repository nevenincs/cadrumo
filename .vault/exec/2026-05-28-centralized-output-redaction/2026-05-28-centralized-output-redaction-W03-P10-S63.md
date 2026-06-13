---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S63'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update live IVA wallet inspector tests for central redaction of identifiers

## Scope

- `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`

## Description

- Validate IVA wallet inspector CLI tests against centralized redaction and real wizard/project-answer registration.
- Ensure lazy `aeat app modelo` command loading imports the real wizard catalogue and persistence registration modules before `work create` touches `SETUP_FLOW`.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_iva_wallet_inspector.py` passed: 16 passed.
- `uv run pytest -q src/aeat/application/modelo/test_actions.py::test_iva_wallet_blocked_exception_carries_translated_message_key src/aeat/entrypoints/cli/test_iva_wallet_inspector.py` passed: 17 passed.

## Notes

- The repair uses production import side effects from `aeat.application.wizard._catalogue` and `aeat.application.wizard._persistence`; no fake catalogue, monkeypatch, or test-only registration hook was added.
