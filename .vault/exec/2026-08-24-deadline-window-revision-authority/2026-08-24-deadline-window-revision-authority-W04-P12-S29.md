---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:38c9af19305a10e28a2eaeac54fcc336b9b296d1334282ae9a706d6512444b1a'
step_id: 'S29'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Audit overview, workflow, and filing-window consumers for exclusive canonical deadline API use

## Scope

- `src/cadrumo/application/`

## Description

- Locate deadline consumers and governing ADRs with Vaultspec RAG.
- Confirm every result with exact-symbol searches and whole-file reads.
- Distinguish observational evidence reconciliation from legal-obligation deduplication.
- Replace workflow first-match selection with fail-closed exact-one selection.
- Add a planted duplicate schedule regression.

## Outcome

- Overview calendar, agenda, backlog, explain, work posture, and workflow consume `DeadlineEngine`, `resolve_filing_closes_on`, or `resolve_filing_window`.
- No local revision selector, qualifier matcher, cadence generator, period parser, deadline catalogue, or obligation dedupe remains.
- Workflow raises `ScheduleComputationError` if an exact work target appears more than once in the canonical schedule.
- Implementation and regression were captured in concurrent commit `73346a8654`.

## Notes

- Evidence/event dedupe in `_calendar_evidence.py` is legitimate reconciliation and does not alter legal schedule multiplicity.
- An unrelated workflow precondition expectation drift was observed during the broad focused run and was not modified.
