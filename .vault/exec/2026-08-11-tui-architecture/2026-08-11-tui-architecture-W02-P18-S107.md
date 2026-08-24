---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b581d5cd1fc830049fb9c8f4753c73314f27a69ba5e5e2fbe0425b9852ba6396'
step_id: 'S107'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Remove the duplicate profile-local TUI option and align password boundary tests

## Scope

- `src/cadrumo/entrypoints/cli/_config`
- `src/cadrumo/core`
- `src/cadrumo/application/user_profile`
- `src/cadrumo/adapters/inbound/tui`

## Description

Remove the duplicate profile-local option and lower the canonical profile-password scalar floor to eight.

## Outcome

Profile create/edit retain automatic terminal routing; explicit TUI selection belongs only to the root. Password boundaries are 7/8/256/257.

## Notes

The broad integration run exposed concurrent recovery-enrollment fixture drift in password CLI tests; core and application password policy tests remain green.
