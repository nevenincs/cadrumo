---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:97c647c4451bd1a0ba3d0ef460331e15d7ffc3105ca00ff425f50f5e7109269f'
step_id: 'S11'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden filing-periods.md

## Scope

- `docs/how-to/filing-periods.md`

## Description

- Verify-close: read `filing-periods.md` against its 2026-06-18-audit finding m10 and confirm resolution at HEAD.
- Confirm m10 (`0A` listed as a common token while a 303-scoped rejection lists only `1T`-`4T`/`01`-`12`): the page now states explicitly that "which tokens a modelo accepts is modelo-specific, not universal" - a quarterly modelo like 130 accepts only `1T`-`4T`; an annual modelo like 390 accepts only `0A`; Modelo 303 accepts `1T`-`4T` and `01`-`12` but NOT `0A` - and points to `aeat app modelo describe` to read a modelo's `Períodos` line.
- Confirm the calendar-shape rejections (`2026Q1`, bare `2026`) are documented with the `--year` + `--period` fix.

## Outcome

- Page verified compliant at HEAD; finding m10 resolved. Delta: none required. CLI conformance gate green.

## Notes

- The period-token grammar is grounded in the single Period boundary authority. AEAT tokens documented precisely.
