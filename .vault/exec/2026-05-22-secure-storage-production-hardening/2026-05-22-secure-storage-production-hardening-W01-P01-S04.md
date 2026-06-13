---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W01.P01.S04`

Added a real-entrypoint custody regression test for the profile lifecycle
surface.

- Created: `src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py`

## Description

The new test runs the real CLI entrypoint in subprocesses with an isolated
file-backed secret store. It proves `profile create` provisions `master.key`,
`master.kdf`, and `salt`; `profile logout` succeeds; `profile switch` reopens
the profile under the same passphrase; and the retired `config init` surface is
not present.

## Tests

Ran:

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py -q`

Result: 1 passed.
