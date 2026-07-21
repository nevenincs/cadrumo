---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S98'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Preserve config profile logout as the sole strong local-session logout command

## Scope

- `src/cadrumo/entrypoints/cli/_config/__init__.py`

## Description

- Retain `config profile logout` as the sole command that closes the active storage session.
- Preserve session close, in-memory key disposal, bucket-engine disposal, and pointer clearing through the canonical profile orchestration.
- Keep the canonical logout registered as destructive in the operator risk authority.

## Outcome

The strong profile logout path remains the only live logout authority and retains the full storage-session teardown semantics.

## Notes

Verified with the real persisted custody lifecycle suite: 6 tests passed.
