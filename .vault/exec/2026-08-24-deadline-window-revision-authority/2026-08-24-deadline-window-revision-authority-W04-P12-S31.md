---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e8b1b3ef015e9fcd2082aac719e54793bed4c2186d59d9706ee0dc6cb9aa0044'
step_id: 'S31'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Add real CLI JSON regressions for calendar, agenda, backlog, workflow, and explain including exactly four M303 quarterly obligations for 2025

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Discover the canonical real-CLI fixtures and typed JSON projections with `vaultspec-rag` before editing.
- Pin the calendar JSON projection to the ordered four-row Modelo 303 filing-year 2025 schedule.
- Pin agenda and backlog JSON cohorts to the same ordered Modelo 303 semantic coordinates without set or dictionary normalization.
- Drive four real `modelo work create` invocations and prove every quarter binds through canonical `select_revision`.
- Prove `overview explain` emits the Modelo 303 2025 result and engine-owned scheduling rationale without inventing a command-local deadline list.
- Run the five focused integration regressions together and Ruff over every changed CLI test module.

## Outcome

Every named real CLI JSON surface now has an executable deadline-authority witness. Calendar, agenda, and backlog each preserve exactly `2025 1T` through `2025 4T`; workflow resolves each quarter once to the registry-selected revision; explain preserves its native single-modelo contract and carries the canonical engine rationale. No CLI-local resolver, parser, cadence map, or deadline DTO was introduced.

## Notes

The five-test integration matrix passed together in 64.25 seconds. Ruff passed over all five participating modules. Agenda uses a 365-day horizon anchored on 2025-02-01 so all four 2025 filing windows, including Q4 closing in 2026, are present. Backlog uses an explicit range through 2026-02-28 and asserts ordered overdue items.
