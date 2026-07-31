---
tags:
  - '#exec'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:cffb9336501d92b92e48710a908a2726f88f6e8646c80a4cdc5b7cd1a0eba638'
step_id: 'S03'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `W02.P02.S03` Notifications latest facade

## Description

- Add `app live notifications latest` as a local-only read over the persisted notification snapshot service.
- Emit a stable JSON payload when no snapshot exists and when a latest snapshot is present.

## Outcome

The command is registered and live readback found the previously captured one-row notification snapshot.

## Notes

The command does not contact AEAT and does not mutate notification state.
