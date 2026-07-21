---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S25'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

- Write the candidate recovery words directly to the controlling terminal device (`CONOUT$` / `/dev/tty`) via the new `write_to_controlling_terminal` in `src/cadrumo/entrypoints/cli/_config/_secure_input.py`, deliberately bypassing stdout so a redirected stream, JSON envelope, or log can never serialize them.
- Require a full no-echo retype of all 24 words before commit; the storage facade verifies the retype against the staged envelope and installs atomically only on match.
- Refuse `create`/`rotate` cleanly (REFUSED, exit 2, localized) when stdin is not an interactive terminal, before any custody read.

## Outcome

Enrollment is show-once-retype-to-commit: a cancelled, mistyped, or non-interactive attempt leaves the prior envelope byte-identical.

## Notes

The terminal write is registered as an audited exception in the output-surface inventory gate with the secret-serialization rationale.
