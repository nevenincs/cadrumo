---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S70'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update live IVA wallet static privacy guard for shared redaction vocabulary

## Scope

- `src/aeat/application/live/test_iva_wallet_privacy_static_guard.py`

## Description

- Validate the live IVA wallet static privacy guard against the shared redaction vocabulary.
- Confirm the test remains a static privacy scan for valid-looking taxpayer identifiers in live IVA wallet surfaces.

## Outcome

- `uv run pytest -q src/aeat/application/live/test_iva_wallet_privacy_static_guard.py src/aeat/adapters/outbound/llm/test_redaction.py --tb=short -vv` passed: 8 passed.

## Notes

- No production-code changes were required for this row during closeout validation.
