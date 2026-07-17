---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# RAG-ground the calendar module concept, read _calendar.py in full, and identify a cohesive extraction boundary (e.g. per-modelo or per-section calendar builders) that shrinks both the module and build_overview_calendar under their overrides

## Scope

- `src/aeat/application/overview/_calendar.py`

## Description

- RAG-grounded the calendar module concept via `vaultspec-rag search "build overview calendar deadlines" --type code`.
- Read `_calendar.py` in full (1677 lines) and enumerated every top-level `def`.
- Identified two cohesive, self-contained concerns for extraction: the calendar-event dedup pair (`_calendar_event_sort_key`, `_dedupe_calendar_events`) and the filing-evidence-reconciliation surface (`calendar_filing_evidence_from_sources` plus its 26 private helpers and 3 module constants).
- Traced every cross-reference in both directions (grep for each candidate symbol's call sites) to confirm the extraction boundary is one-directional: the staying code calls into the moving code, never the reverse, avoiding a circular import between the shrunk module and its new sibling.
- Confirmed via `grep` that the public `calendar_filing_evidence_from_sources` symbol is consumed only through the package `aeat.application.overview` facade (never `._calendar` directly) by every test file and CLI caller, so the facade re-export needed no changes.

## Outcome

Extraction boundary confirmed and documented: 722 lines (`calendar_filing_evidence_from_sources` through `_calendar_event_filing_evidence`) plus 26 lines (`_calendar_event_sort_key` + `_dedupe_calendar_events`) plus 22 lines (3 module constants) move to a new `_calendar_evidence.py` sibling, mirroring the module's existing `_calendar_models.py` / `_calendar_warnings.py` / `_coverage.py` split pattern.

## Notes

No incidents. Grounding and boundary analysis only; no code changed in this step.
