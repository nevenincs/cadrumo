---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
body_hash: 'sha256:3b3ee81700bdedfe84c24ca224a522c72fd006db39d2a47b51edf410a89a37db'
step_id: 'S442'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Correct Modelo 180 2024 and 2025 deadline-window filing-year keys to the tax-year consumer contract and prove both DeadlineEngine calendar inclusion and same-year work-schedule lookup.

## Scope

- `src/aeat/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/deadline_windows/ src/aeat/{domain/deadlines`
- `application/modelo}/ src/aeat/**/tests/`

## Description

- Grounded annual deadline selection with RAG and source tracing; confirmed cross-calendar workflow targets resolve windows by `target_period.filing_year`.
- Corrected Modelo 180 annual deadline-window keys from campaign years 2025/2026 to tax years 2024/2025, preserving January campaign dates.
- Added real DeadlineEngine coverage for the 2024-to-January-2025 and 2025-to-January-2026 campaigns.
- Added a full WorkflowEngine M180/2024 target run during January 2025.
- Ran focused deadline/workflow and M180 registry suites with owned Ruff and scoped whitespace verification.

## Outcome

- Modelo 180 annual windows now share the tax-year key used by the deadline engine and workflow target period.
- Direct engine and workflow paths both find the legal January campaign for the original tax year.
- Focused deadline/workflow coverage passed 62 tests in 28.08 seconds; M180 registry coverage passed 9 tests in 14.93 seconds; owned Ruff and whitespace checks passed.

## Notes

- This repair is intentionally separate from S441 because Modelo 100 and Modelo 180 have independent registry revisions and historical evidence.
