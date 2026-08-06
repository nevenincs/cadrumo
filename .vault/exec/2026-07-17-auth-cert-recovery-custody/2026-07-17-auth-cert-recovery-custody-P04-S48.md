---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:28709970441e68f2454f09265673276a4e082502c384bf97157675a5ffdb5e9f'
step_id: 'S48'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Discriminate a real console from a bare character device before prompting, so a NUL or console-less stdin refuses instead of blocking forever in msvcrt.getwch, and apply the same precondition to the recovery-code terminal display

## Scope

- `src/cadrumo/entrypoints/cli/_config/_secure_input.py`

## Description

- Probe four real spawn shapes to establish an honest discriminator rather than
  assuming one: a real console, a `NUL` stdin, a pipe stdin, and a console-less
  detached host.
- Add a module-private real-console precondition to the custody secret-input module.
  The console-mode query succeeds only for a genuine console handle and fails with
  an invalid-handle error for both non-console character devices, separating them
  exactly.
- Gate both terminal-facing custody functions on it: the no-echo prompt and the
  recovery-code terminal display.
- Fail closed. When the probe cannot be completed the answer is "not a console",
  because the purpose is to never reach a promptable-looking channel that cannot be
  typed into. Non-win32 defers to the existing interactive check, since the POSIX
  path opens the terminal device itself and surfaces a real failure instead of
  blocking.
- Add a hang regression that spawns a genuine detached process and fails on timeout.
- Re-isolate the echo-suppression regression. The new precondition now runs first, so
  a fake-console channel can no longer reach that guard; the test moves to the one
  channel where it decides, a true console whose standard input an upstream layer has
  rebound through a second genuine console-input handle.

## Outcome

A custody prompt on a channel with no console behind it now refuses promptly instead
of blocking forever. Six tests pass in the echo-guard module, the four locale gates
pass, and the recovery-lifecycle suite passes 5 of 5.

The hang regression fails on timeout rather than passing, so a reintroduced block
cannot slip through by hanging. The echo regression asserts its three preconditions
(real console, interactive, rebound) before asserting the refusal, so it cannot pass
by silently degrading into the non-interactive case.

## Notes

This closes the gap the preceding Step's record disclosed as uncovered: the
console-less path previously had no test, because the failure mode was an indefinite
block rather than an exception and any naive test would have hung the suite.

The originating review predicted an error from the low-level console read on a
console-less host. That does not reproduce here. The read blocks instead, which is
worse: an operator can neither satisfy nor diagnose it. The root cause is upstream of
the prompt entirely - the interactive check returns true for a character device with
no console behind it, a false positive in the precondition.

Duration was explicitly rejected as the instrument. A timeout on a secret prompt would
abandon a passphrase mid-entry, and a twenty-four word mnemonic is legitimately slow
to type. Detection is the correct layer.

The recovery-code display carried the same defect with a worse consequence than the
prompt: opening the console output device succeeds against a console-less host, so the
candidate words would have been written to a console the operator never sees while the
verb reported success. The words are shown exactly once and are unrecoverable
afterwards, so that path was silent, permanent loss rather than an inconvenience.

An earlier pass concluded the console-mode query could not discriminate these cases.
That conclusion was wrong and was caused by omitting the foreign-function argument and
return types, which made every call report failure including the real console. Setting
them explicitly produced clean separation.
