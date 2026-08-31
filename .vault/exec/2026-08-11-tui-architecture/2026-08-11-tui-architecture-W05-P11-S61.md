---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:16523c0d5e6b1b219352d64af8ae7db50efe2c9e8a2925c49935f68bc036ee7a'
step_id: 'S61'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Project only OperationPublicProjectionV1 and its public capability and refusal fields into immutable modal view models without importing persisted snapshots, journal records, or supervisor-private state

## Scope

- `src/cadrumo/entrypoints/tui/operations/projection.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/operations/projection.py`
