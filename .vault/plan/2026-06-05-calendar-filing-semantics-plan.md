---
tags:
  - '#plan'
  - '#calendar-filing-semantics'
date: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
  - '[[2026-06-05-calendar-filing-semantics-reference]]'
  - '[[2026-06-04-calendar-live-filing-integration-reference]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `calendar-filing-semantics` `implementation` plan

## Wave `W01` - evidence model correction

Make the calendar represent the difference between local ready-to-file state and actual AEAT-submitted evidence.

### Phase `W01.P01` - typed calendar evidence

Add typed evidence fields to calendar entries and events without changing the legal deadline status taxonomy.

- [x] `W01.P01.S01` - Add calendar filing-evidence models and pure evidence merge helpers; `src/aeat/application/overview/__init__.py`.
- [x] `W01.P01.S02` - Wire CLI calendar storage reads from local Modelo records and calculation observations; `src/aeat/entrypoints/cli/_overview.py`.

## Wave `W02` - contracts and verification

Prove the corrected semantics in application and CLI tests, then run review and live-safe verification.

### Phase `W02.P02` - proof and closeout

Add regression tests that prevent conflating local filed records with AEAT-submitted/justificante-verified returns.

- [x] `W02.P02.S03` - Add application and CLI regression tests for dual filing states; `src/aeat/application/overview/tests/test_calendar.py`.
- [x] `W02.P02.S04` - Run focused gates, live-local calendar verification, execution records, and code review; `.vault/exec/2026-06-05-calendar-filing-semantics`.

## Wave `W03` - taxpayer-bound justificante verification

Close the continuation gap where Modelo external evidence could mark calendar entries as justificante-verified without persisted taxpayer-bound justificante metadata.

### Phase `W03.P03` - metadata-bound calendar verification

Require calendar verificante state to come from secure persisted justificante metadata matched to the rendered taxpayer.

- [x] `W03.P03.S05` - Bind calendar justificante verification to persisted metadata and active taxpayer; `src/aeat/application/overview/_calendar.py, src/aeat/entrypoints/cli/_overview.py, src/aeat/application/overview/tests/test_calendar.py, src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`.
- [x] `W03.P03.S06` - Bind live filed-declaration evidence to authenticated taxpayer identity; `src/aeat/application/overview/_calendar.py, src/aeat/application/overview/tests/test_calendar.py`.

## Description

This continuation plan addresses the clarified domain gap: a Modelo filing calendar entry must show the legal obligation, the local application readiness state, and the real-world AEAT submission evidence state separately. AEAT-submitted status requires imported or observed AEAT evidence; justificante verification is stricter and must remain visible as its own boolean/state.

## Steps

## Parallelization

S01 and S02 are sequential because CLI wiring depends on the typed evidence model. S03 can be written alongside S02 once field names are stable. S04 runs last.

## Verification

- Calendar entries expose local filing state and AEAT submission evidence independently.
- A local `ModeloRecord` without external evidence never appears as AEAT-submitted or justificante-verified.
- An imported justificante-backed filing appears as AEAT justificante-verified.
- An expedientes snapshot appears as AEAT submitted-observed even when no justificante has been verified.
- Focused ruff and pytest pass for overview application/CLI paths.
- Code review audit records no HIGH or CRITICAL findings.
