---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:2fe851ca61db8757ffd886e0d6765fba464bf4aafa364ca48979b3fdfc45d3b0'
step_id: 'S13'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Drive the line-mode frontend headlessly through pipe input and assert prompt, validation, and refusal behavior

## Scope

- `src/cadrumo/application/flows/tests/test_line_frontend.py`

## Description

- Drive the line-mode frontend headlessly through piped input, asserting prompt rendering, per-answer validation, and the unsupported-console refusal.
- Cover the secret-echo masking and Ctrl-C cancellation cases against real injected streams.
- Landed in `10506c8833` (test_line_frontend.py, 8 tests); masking and cancel cases added in `2b2c93bf90`.

## Outcome

The line frontend has real-behavior headless coverage over injected IO: prompts, validation verdicts, refusal, secret masking, and typed abandonment all assert against live output with no mocks.

## Notes

None.
