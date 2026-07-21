---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S30'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`

## Description

- Extend `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py` with a parametrized contract that every custody secure-input refusal key (non-interactive secret, stdin too large / invalid JSON / missing fields, interactive-terminal-required, retype mismatch, recovery-code rejected) resolves to non-placeholder operator copy.
- Prove strict bounded `--secrets-stdin` behavior through localized CLI execution in the recovery lifecycle suite: malformed JSON, non-object payloads, and unexpected fields refuse (exit 2) with no traceback.

## Outcome

Secure-TTY and bounded-stdin failures surface as localized REFUSED exits across the recovery family.

## Notes

None.
