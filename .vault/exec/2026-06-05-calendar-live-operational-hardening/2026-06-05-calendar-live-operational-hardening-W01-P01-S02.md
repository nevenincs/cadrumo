---
tags:
  - '#exec'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
step_id: 'S02'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `W01.P01.S02` Modelo 721 unsupported boundary

## Description

- Add a conservative filed-capture unsupported boundary for Modelo 721.
- Return a structured bulk failure row before live session acquisition when only unsupported modelos are requested.
- Add a production-service test that exercises the Modelo 721 boundary without fakes or auth.

## Outcome

`filed capture-all --modelo 721` reports one explicit local failure row and does not silently omit the modelo or waste a remote AEAT traversal.

## Notes

The boundary matches the current registry construct, which declares no filed-declarations live read surface for Modelo 721.
