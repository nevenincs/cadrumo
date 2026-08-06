---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:97429b1d7f2c25be9913ca5f4bbe6b7f7e7986f3b8dac96ac16c324fa2837a52'
step_id: 'S11'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Build the sequential line-mode frontend over the engine, absorbing the questionary prompter role and retaining the translated unsupported-console refusal and IO-injection contract

## Scope

- `src/cadrumo/application/flows/_line_frontend.py`

## Description

- Walk the engine sequentially through a line-mode frontend that absorbs the questionary prompter role over an injectable IO contract.
- Retain the translated unsupported-console refusal so headless and non-TTY callers meet an instructive message, not a traceback.
- Landed in `86cd98ef84`, hardened by review fixes `2b2c93bf90` (secret-echo masking, Ctrl-C typed abandonment) and `81e892e612` (post-commit answer hook for mid-walk locale switch).

## Outcome

The line-mode frontend drives any FlowDefinition over injected streams, masks secret answers, and treats Ctrl-C as a typed abandonment rather than an uncaught interrupt. The console refusal stays localised.

## Notes

Secret masking and the typed-abandonment path were review findings landed after the initial commit; both ride `2b2c93bf90`.
