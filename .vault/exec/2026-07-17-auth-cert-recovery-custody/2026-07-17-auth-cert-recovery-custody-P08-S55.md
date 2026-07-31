---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:11612b749ddcd66a9608faa13a452addece37c63ac6acda2976dc35e2016faaf'
step_id: 'S55'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Cover the 8192-byte secrets-stdin size cap with an oversize-input regression, the one bound the existing bounds tests never exercise while covering malformed input, wrong fields, and non-object payloads

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`

## Description

- Add a real-CLI oversize regression to `test_config_recovery_lifecycle.py`,
  driving `config recovery verify --secrets-stdin` with a payload past the
  8192-byte cap and asserting a clean refusal (exit 2, no traceback) rather
  than a hang, a crash, or an unbounded read.
- Confirm `test_tty_error_locale.py` already parametrizes
  `cli.config.custody.errors.secrets_stdin_too_large` in its locale-resolution
  coverage, so nothing further was added there.
- Add a companion duplicate-key regression in the same location for the
  neighbouring `P08.S52` step, since both close bounded-strict-JSON gaps in
  the same module and share the same real-CLI harness.

## Outcome

The oversize branch of `_MAX_SECRETS_STDIN_BYTES` in `_secure_input.py` is now
proven by driving the real CLI subprocess harness with a payload over the
cap: refuses cleanly (exit 2, no traceback) instead of the previously
unexercised path. Verified together with the S52 duplicate-key regression;
both tests pass, `test_config_recovery_lifecycle.py` collects 7 tests (up
from 5), and the full module run passes (7 passed in 191s under xdist).

## Notes

Divergence from the Step's named file: the plan Step names
`src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`, but that module
tests locale-KEY resolution only (that
`cli.config.custody.errors.secrets_stdin_too_large` resolves to non-placeholder
copy), not real CLI byte-cap enforcement — it carries no subprocess harness.
That module already covers the locale-key axis and needed no change. The
substantive real-CLI oversize gate was placed in
`test_config_recovery_lifecycle.py` instead, next to the existing
`test_recovery_secrets_stdin_is_strict_bounded_json` bounds test, because that
module already owns the `_run_cli` subprocess harness this gate needs to drive
the real 8192-byte read path end to end.
