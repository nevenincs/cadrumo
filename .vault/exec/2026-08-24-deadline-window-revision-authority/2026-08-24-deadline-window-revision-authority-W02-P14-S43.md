---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b785205a1d4212c3f0f73f8a2e061b56b11219594d9ddd2bf70ae11076887991'
step_id: 'S43'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 216 deadlines for supported filing years 2022-2026 and materialise all 4 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/216/`

## Description

- Lead discovery with Vaultspec RAG, read the complete M216 revision surfaces, and confirm all canonical authorities with exact-symbol searches.
- Re-adjudicate the supported 2024-2026 quarterly corpus against the bundled official AEAT calendars and binding procedure.
- Materialise exactly the four measured 2024 quarterly cells and correct the two stale 2025 weekend closing dates.
- Add published direct-debit cutoffs only where an applicable bundled calendar exists; retain no cutoff claim for 2026 `4T` without a bundled 2027 calendar.
- Close calendar-source provenance through the owning revision and construct.
- Add exact census, date, source, typed-period, and canonical-owner regressions.
- Run focused registry validation, ownership tests, Ruff, Vaultspec RAG redeclaration audit, and isolated architecture review.

## Outcome

Modelo 216 now has exactly twelve canonical quarterly deadline coordinates for its supported filing years 2024 through 2026. The four previously missing 2024 coordinates are grounded in the bundled AEAT 2024 and 2025 calendars. Calendar-published business-day extensions correct 2025 `1T` and `2T`, and direct-debit cutoffs are present only when the bundled calendars publish them.

No selector, resolver, period parser, cadence mapping, supported-year horizon, or deadline catalogue was introduced. Registry facts and regressions reuse `Period`, `registry_period_kind`, `PeriodKind`, `select_revision`, the existing source catalogue, and fragmented deadline loading.

## Notes

Modelo 216's only revision begins in 2024, so 2022 and 2023 are outside its declared temporal and period-selector coverage rather than missing deadline cells. The 2026 `4T` row retains its binding official procedure source and no payment cutoff: its physical filing window is in 2027, for which no contributor calendar is bundled.
