---
tags:
  - '#exec'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S04'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `W02.P02.S04` Expedientes capture-all facade

## Description

- Add an application bulk expedientes capture service that shares one authenticated declarations-register session across modelo/year queries.
- Add `app live expedientes capture-all` with repeated `--modelo` filters and explicit failure rows.

## Outcome

The command is registered and reaches the live auth flow. Fresh AEAT verification is blocked by current Cl@ve Móvil approval timeouts.

## Notes

The service persists one aggregate snapshot for the whole bulk refresh and remains read-only.
