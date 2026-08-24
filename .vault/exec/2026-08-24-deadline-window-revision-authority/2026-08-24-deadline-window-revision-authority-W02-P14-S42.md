---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a8cacba52db965c1203ddd559c3bbba6cbb2c7802677ed0878c45757a99cbb35'
step_id: 'S42'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 202 deadlines for supported filing years 2022-2026 and materialise all 9 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/202/`

## Description

- Lead discovery with Vaultspec RAG, read the complete M202 revision surfaces, and confirm canonical authorities with exact-symbol searches.
- Extract the bundled official AEAT 2022-2024 contributor calendars and transcribe only their published M202/M222 filing and direct-debit dates.
- Materialise the nine measured 2022-2024 `1P`/`2P`/`3P` windows in their `select_revision` owners.
- Close revision, construct, source, and deadline-application-link provenance for all supported 2022-2026 M202 windows.
- Add exact census, date, source, typed-period, and canonical-owner regressions.
- Run focused registry validation, ownership/identity tests, Ruff, Vaultspec checks, and an isolated architecture review.

## Outcome

Modelo 202 now has exactly fifteen supported-year deadline coordinates: three canonical instalment periods for each filing year from 2022 through 2026. The nine previously missing coordinates are grounded in the bundled official calendars; all fifteen rows carry their year-specific calendar citation and resolve to their containing revision through `select_revision`.

No selector, resolver, period parser, cadence mapping, supported-year horizon, or deadline catalogue was introduced. The data and tests consume the existing `Period`, `registry_period_kind`, `PeriodKind`, and `select_revision` authorities.

## Notes

The earlier family dispositions incorrectly stated that the 2022 calendar was absent; the official PDF was already bundled and readable. Those dispositions were removed when their families became populated. The schema-level deadline `period_kind` remains `quarterly`, while canonical token classification correctly reports `PeriodKind.INSTALMENT`; this preserves the existing deadline schema and avoids creating a second cadence vocabulary.
