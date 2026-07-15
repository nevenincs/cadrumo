---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S433'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Migrate live Period.year consumers to filing_year, remove the compatibility alias, and prove the period, calendar, workflow, and CLI surfaces retain their contracts.

## Scope

- `src/aeat/core/_period.py src/aeat/{application`
- `domain`
- `entrypoints}/ src/aeat/**/tests/`

## Description

- Used the RAG index and source search to enumerate direct and indirect `Period.year` consumers, including an overview `getattr` reached by the real CLI.
- Removed the `Period.year` compatibility alias and migrated core, workflow, aggregation, overview, calendar, deadline, modelo, filing, calculation-sheet, and CLI consumers to `filing_year`.
- Reconciled direct tests to assert the canonical field and added a core contract that a typed period has no `year` attribute.
- Ran the focused CLI integration suite, core/domain contract suite, broader non-CLI suite, owned Ruff, and scoped whitespace verification.

## Outcome

- `filing_year` is the only typed period-year vocabulary; the compatibility alias and its active consumers are removed.
- Focused CLI integration passed 72 tests, core/domain contract coverage passed 68 tests, and the broader non-CLI slice passed 351 tests.
- Owned Ruff and scoped whitespace checks passed.

## Notes

- Twenty-five unrelated review-adapter tests cannot open their local encrypted fixture because the shared live-store master key at `C:\Users\hello\AppData\Local\aeat\live-store-v2\secret` mismatches. The same failure occurs with single-worker execution before Period-path assertions; this step does not alter that store or classify it as a typed-period defect.
