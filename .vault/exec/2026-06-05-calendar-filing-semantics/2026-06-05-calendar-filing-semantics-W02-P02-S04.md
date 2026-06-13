---
tags:
  - '#exec'
  - '#calendar-filing-semantics'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S04'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` `W02.P02.S04`

Scope: run focused gates, live-local calendar verification, execution records, and code review.

## Description

- Run focused lint over overview, filed-declaration store, payload, and CLI test files.
- Run focused overview application and CLI regression tests.
- Run authenticated live AEAT filed-history list for Modelo 303 ejercicio 2024.
- Run authenticated live AEAT filed capture-all for Modelo 303 ejercicio 2024.
- Run authenticated live AEAT expedientes capture-all for Modelo 303 ejercicio 2024.
- Run authenticated live AEAT notifications capture.
- Run all-profiles overview calendar in text and JSON modes after live captures.
- Resolve code-review findings and record their closure in the audit.
- Resolve follow-up review findings by validating stored justificante artefact bytes before calendar verification and typing nested calendar JSON payload schemas.
- Add duplicate-expediente regression so event-level justificante verification is keyed by AEAT reference, not only Modelo/year/period.
- Close the final plan step through `vaultspec-core`.

## Outcome

The calendar now reports AEAT filing events as `justificante_verified` only when the encrypted filed-declaration observation store contains a matching loadable `justificante_pdf` artefact whose byte count and SHA-256 match the manifest. Live Modelo 303 2024 history returned six AEAT rows, filed capture recorded six observations with zero failures, expedientes capture recorded six declarations with zero failures, notifications capture recorded one message, and the final calendar aggregation surfaced six filing events with `justificante=true` plus one message event.

## Notes

The shared live profiles remain incomplete for taxpayer-model derivation, so the final all-profiles calendar contained zero legal deadline entries and seven observed events. Entry-level evidence is covered by deterministic application tests; event-level live evidence was verified through the real CLI output. One successful expedientes capture emitted a Playwright target-closed cleanup log after completion. Focused tests finished at 71 passing after the follow-up fixes.
