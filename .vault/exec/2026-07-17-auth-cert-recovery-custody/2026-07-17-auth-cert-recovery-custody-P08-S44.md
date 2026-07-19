---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S44'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# DEFERRED until the operator P04 passphrase door commits: make certificate secret set reject the passphrase as an argv value and read it only via the hidden prompt or bounded stdin, reusing the P04 door _secure_input.py bounded-stdin no-echo infrastructure rather than building a parallel secret-input authority, gated on a test proving the passphrase cannot be supplied as an argv value and is read only through hidden prompt or bounded stdin

## Scope

- `src/cadrumo/entrypoints/cli/_config/_certificate.py`

## Description

- Remove the `--secret` argv option from `certificate secret set`; the PKCS#12 passphrase now arrives only via the hidden no-echo prompt or one bounded strict-JSON `--secrets-stdin` object, reusing the shared `_secure_input` channel (no parallel secret-input authority).
- Migrate every `test_certificate.py` invocation to the stdin channel and add gates proving the argv passphrase is refused, the no-TTY/no-stdin path refuses cleanly naming `--secrets-stdin`, and the help names only secure channels.

## Outcome

Certificate suite green (16 tests including 3 new gates); the passphrase can no longer land in the process table or shell history.

## Notes

Landed after the P04 passphrase door committed, per the Step's deferral condition.
