---
tags:
  - '#exec'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S05'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `W02.P02.S05` Payload schemas and tests

## Description

- Add strict payload schemas for notifications latest and expedientes capture-all.
- Add CLI help and registration tests for both new facades.

## Outcome

Focused CLI tests pass and the commands are discoverable through the Click command tree.

## Notes

The broad JSON schema conformance test still fails on a pre-existing suite-wide discovery gap covering many ledger, config, and live leaves.
