---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:2819658a7c82a546cb6c57ef92148eaec2ea25d326ff2ca39d657ac1544d33cb'
step_id: 'S32'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Add all-modelo parity coverage across registry, DeadlineEngine, overview, workflow, and real CLI for every supported filing year

## Scope

- `src/cadrumo/domain/deadlines/tests/`
- `src/cadrumo/application/overview/tests/`
- `src/cadrumo/application/workflow/tests/`
- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Discover existing fleet invariants, profile projections, real CLI fixtures, and the supported-year owner with `vaultspec-rag` before editing.
- Broaden the registry-to-engine fleet invariant from periodic rows to every unqualified pre-calculation deadline row.
- Derive expected engine rows through canonical filing-schedule and profile-condition evaluators for each catalogue-supported filing year.
- Compare the workflow pending-obligation projection with the ordered production schedule for every supported year.
- Compare overview entries with every applicable engine row on modelo, period, legal dates, payment cutoff, and status for every supported year.
- Compare real CLI JSON calendar rows with the application projection on every operator-visible deadline coordinate for every supported year under one execution-date snapshot.
- Preserve qualified M210 plazo variants as post-calculation resolution rather than forcing them into the pre-calculation schedule.
- Run focused unit and integration matrices and Ruff over all changed modules.

## Outcome

The registry, engine, workflow, overview, and real CLI now carry one executable fleet parity chain whose year horizon comes exclusively from `catalogues.supported_filing_years`. Expected registry rows reuse `deadline_semantic_coordinate`, `applicable_filing_schedules`, and `evaluate_profile_conditions`; downstream tests consume the engine and application projections without adding a resolver, cadence map, modelo list, or deduplicator. Missing, duplicate, reordered, or altered rows fail at the relevant boundary.

## Notes

The focused unit matrix passed four tests, including both monthly-IVA profile variants, in 65.87 seconds. The generalized five-year real CLI integration passed in 261.44 seconds. It captures `today_madrid()` once at execution time and shares that transient value through the CLI clock seam and expected projection, so no calendar date becomes a durable test fact and a midnight rollover cannot split the comparison. Ruff passed over all four changed modules. The CLI's native calendar summary intentionally exposes adjusted close, payment cutoff, and status rather than raw `opens_on` and `closes_on`; raw legal-date parity remains proven at the application boundary.
