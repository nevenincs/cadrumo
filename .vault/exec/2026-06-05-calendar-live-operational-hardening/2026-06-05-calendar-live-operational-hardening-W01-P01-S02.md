---
tags:
  - '#exec'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:82d02b979a75a0657cbf8502f99b43f7e5faf56313575808a8821f534cdac663'
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

The boundary is derived from registry revision metadata. Follow-up verification also proved Modelo 151 reports locally when its 2024 revision lacks a filed-declarations live read surface.
