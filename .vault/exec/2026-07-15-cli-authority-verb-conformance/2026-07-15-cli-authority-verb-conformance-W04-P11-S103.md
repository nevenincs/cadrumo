---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:6708e12897d1e94bf6cfb68ace06ced59f3c6385ead39cbcfb944d2a5b1fd081'
step_id: 'S103'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove switching and strong logout through real persisted custody state

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`

## Description

- Create a real encrypted profile through the public CLI.
- Execute strong profile logout in a fresh process and prove the retired root lock command is unavailable.
- Re-select the same profile by exact label and through the default pointer path.

## Outcome

Switching and strong logout are proven through real persisted custody state with no duplicate command door.

## Notes

The focused integration file completed with 6 passing tests in 185.63 seconds.
