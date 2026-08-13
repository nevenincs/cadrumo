---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:7d6970bbfe885bfedff373d0609270dac226e5d73c99dc74bfb17441dc3d0d4c'
step_id: 'S38'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Wire aeat app live notifications document view taking the certificado id as a positional Argument and reading only the persisted record and its parse, making no AEAT contact at all, verified by a CLI integration test asserting the verb completes with no session factory available

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`

## Description

- Completed local encrypted-custody read-back with no authentication or AEAT session path. Verified the route against real isolated profile storage.

## Outcome

Delivered and verified within the Step's declared scope.

## Notes

RAG discovery was attempted first but unavailable because service compute admission was quiesced. Grounding continued from the accepted decisions, existing execution records, source, targeted symbol search, and live CLI behaviour.
