---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S71'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update LLM redaction tests for shared redaction vocabulary

## Scope

- `src/aeat/adapters/outbound/llm/test_redaction.py`

## Description

- Validate LLM cache and usage redaction tests against the shared redaction vocabulary.
- Confirm NIF and bearer-token canaries are redacted while cached JSON/JSONL records remain parseable.

## Outcome

- `uv run pytest -q src/aeat/application/live/test_iva_wallet_privacy_static_guard.py src/aeat/adapters/outbound/llm/test_redaction.py --tb=short -vv` passed: 8 passed.
- The LLM redaction tests covered cache plaintext absence, bearer-token redaction, parseability, idempotent reread, usage redaction, and one-record-per-JSONL-line behavior.

## Notes

- No fake provider mutation or monkeypatch shortcut was introduced; the tests exercise the existing cache and usage serialization paths.
