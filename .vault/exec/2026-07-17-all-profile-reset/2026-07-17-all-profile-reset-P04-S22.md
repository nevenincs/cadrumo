---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S22'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Prove exact sandbox labels work through switch while sandbox use and bare names are absent

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_profile_sandbox.py`

## Description

- Rewrite the active-indicator-after-switch test to enter the sandbox by its canonical `sandbox:<name>` label through `config switch` instead of the removed `sandbox use`.
- Add `test_sandbox_use_command_is_absent` (invocation fails, `use` absent from the sandbox help), `test_switch_rejects_a_bare_sandbox_short_name`, and `test_switch_accepts_a_sandbox_bucket_uuid`.

## Outcome

The suite proves exact sandbox labels resolve through `switch`, a bucket UUID resolves through `switch`, a bare sandbox short name refuses, and `sandbox use` is absent with no alias. 44 passed against real per-bucket encrypted storage (no mocks).

## Notes

Co-committed with S19 (the removal these tests prove absent).
