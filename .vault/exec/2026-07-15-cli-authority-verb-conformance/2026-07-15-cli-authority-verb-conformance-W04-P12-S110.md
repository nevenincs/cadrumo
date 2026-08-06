---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:175767b72a640e3b8335a8a32028fc76d18a95a4b9a30783dfdf3f9fdc4139d3'
step_id: 'S110'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove passphrase change through a real encrypted vault

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_config.py`

## Description

`config passphrase change` needed a real-behavior round-trip proof: a genuine encrypted
profile provisioned, its passphrase rotated through the CLI, the profile then only
readable under the new passphrase, and a wrong-current-passphrase retry refused without
disturbing access.

## Outcome

`test_config_passphrase_change_round_trips_file_custody`
(`src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py:206-288`)
provisions a real profile via `config profile create`, rotates the passphrase via `config
passphrase change --secrets-stdin` (stdin JSON, never argv), asserts the profile is
readable under the rotated passphrase (`config profile show`) and unreadable under the old
one, and asserts a wrong-current-passphrase retry exits 2 while leaving the profile
readable under the rotated value. The rotated value never appears in command output. This
is a real subprocess-driven CLI run against a real encrypted secret store, not a mock.

## Notes

**Scope discrepancy:** the step's declared scope names
`src/cadrumo/entrypoints/cli/_config/tests/test_config.py`, but that file carries only the
TTY/non-interactive-refusal tests for `passphrase change`
(`test_passphrase_change_without_interactive_stdin_refuses_instructively` and the JSON
refusal variant, lines 333-399); the real-encrypted-vault round-trip this step calls for
lives in `test_config_custody_profile_lifecycle.py` instead. The step's substantive claim
is satisfied by that test; the file it names is not the one carrying it. Cited the
coordinator's gate results (serial `-n0` lane 27 passed/1 failed, unrelated S112 failure)
rather than re-running the suite myself.
