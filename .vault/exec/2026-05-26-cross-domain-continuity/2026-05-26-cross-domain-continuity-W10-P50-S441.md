---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
step_id: 'S441'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Correct Modelo 100 2020 and 2021 deadline-window filing-year keys to the tax-year consumer contract and prove both DeadlineEngine calendar inclusion and same-year work-schedule lookup for their following-year campaigns.

## Scope

- `src/aeat/_data/registry/aeat/modelos/100/revisions/{2020`
- `2021}/deadline_windows/ src/aeat/{domain/deadlines`
- `application/modelo}/ src/aeat/**/tests/`

## Description

- Grounded registry and consumer behavior with RAG and direct source tracing; confirmed workflow selects windows by the work unit's tax-year `filing_year`.
- Corrected Modelo 100 2020 and 2021 deadline-window keys from campaign years to tax years without changing statutory campaign dates.
- Added direct DeadlineEngine regressions for the 2021 and 2022 campaigns, including close and direct-debit dates.
- Added real M100 work-schedule summary regressions proving 2020 and 2021 work units find their own following-year campaign close.
- Ran focused deadline/work-schedule and catalogue-verification suites with owned Ruff and scoped whitespace verification.

## Outcome

- Modelo 100 annual windows now use the same tax-year key as their work units while retaining their correct following-year campaigns.
- `DeadlineEngine.compute(profile, tax_year)` and `modelo_work_plazo_summary` agree for 2020 and 2021 work.
- Focused engine/work-schedule coverage passed 39 tests in 20.93 seconds; catalogue verification passed 18 tests in 14.13 seconds; owned Ruff and whitespace checks passed.

## Notes

- A separate M180 regression already present in the engine test was intentionally not changed; its distinct repair is S442.
