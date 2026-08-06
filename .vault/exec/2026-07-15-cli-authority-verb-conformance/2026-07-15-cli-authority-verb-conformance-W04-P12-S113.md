---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:e92168d2204962e3ea02a4afcdd47ea4aa3ea02dd32f9f3fa88309caf2a98130'
step_id: 'S113'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`

## Description

The secure TTY refusal (`NonTtyRefusedError`) and every custody secure-input refusal key
(non-interactive-secret-required, invalid/oversize/missing-field `--secrets-stdin` JSON,
recovery interactive-terminal-required, retype mismatch, recovery-code rejected) needed to
resolve to real, non-placeholder, localized operator-facing copy through the live CLI
locale catalogue.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py` asserts three contracts:
contract-A (lines 26-52) that `NonTtyRefusedError` carries empty positional `args` so the
CLI renderer falls through to the registry `message_key` rather than the raw exception
text, and that its `suggestion` is preserved; contract-B (lines 63-70) that
`errors.refused.refused_cli_non_tty` resolves through `tr(...)` to non-placeholder copy
longer than 10 characters; contract-C (lines 78-100) parametrizes over the seven custody
secure-input refusal keys (`cli.config.custody.errors.non_interactive_secret_required`,
`secrets_stdin_invalid_json`, `secrets_stdin_missing_fields`, `secrets_stdin_too_large`,
`cli.config.recovery.errors.interactive_terminal_required`, `retype_mismatch`,
`cli.config.recover.errors.recovery_code_rejected`) and asserts each resolves through the
real locale catalogue rather than echoing the raw key.

## Notes

File matches the step's declared scope exactly. Cited the coordinator's gate run rather
than re-executing (serial `-n0` lane 27 passed/1 failed, the unrelated S112 gap). This is a
real locale-catalogue lookup (`tr(...)`), not a mock of the translation layer.
