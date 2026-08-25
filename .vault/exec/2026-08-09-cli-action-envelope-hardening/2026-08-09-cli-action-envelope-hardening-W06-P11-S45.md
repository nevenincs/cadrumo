---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:99d2a75dabca5c2c55e9e4170498f94e76a7d881c0b42a858996d73112ca8f19'
step_id: 'S45'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---




# Enforce the bidirectional declaration and observation join, removing retired error-registry-suggestion test references so only the live canonical citation gate remains.

## Scope

- `dev/tests/test_suggestion_command_conformance.py`

## Description

- Remove retired suggestion-ledger and redaction-suggestion fixtures while retaining the live Click citation gate.
- Join every S42 production declaration to exactly one S43 observation and reject missing, duplicate, or undeclared rows.
- Exercise S44 no-recovery outcomes with a hard-fail dispatch spy.

## Outcome

Commit `eb5fb45fe8` establishes the bidirectional live declaration-observation gate without copied action, command, or schema expectations. It consumes the real production precondition builder and proves explicit no-recovery rows never invoke the CLI dispatcher.

Three targeted integration tests pass; Ruff, format, and diff checks pass. Independent review found no remaining retired citation or authority residue.

## Notes

- The broad live Click-tree citation checks remain in the same module and continue to cover operator-facing command paths.
