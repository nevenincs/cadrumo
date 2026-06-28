---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-21-cli-workflow-redesign-W02-S08]]'
  - '[[2026-05-21-cli-workflow-redesign-W03-S11]]'
  - '[[2026-05-21-cli-workflow-redesign-W03-S12]]'
  - '[[2026-05-22-w02-s08-overview-derivation-review-audit]]'
  - '[[2026-05-22-w03-s11-applicability-review-audit]]'
  - '[[2026-05-22-w03-s12-deadline-review-audit]]'
  - '[[2026-05-22-w03-s13-rate-schedules-review-audit]]'
---

# `cli-workflow-redesign` `taxpayer-type-applicability` summary

Closed the taxpayer entity-type / regime / enrolment model plan at
13 of 13 completed steps, preserving the CLI-managed plan state after
restoring the known L3 row-stripping mutation.

- Modified: `.vault/plan/2026-05-21-taxpayer-type-applicability-plan.md`
- Modified: `src/aeat/application/overview/__init__.py`
- Modified: `src/aeat/application/overview/_applicability.py`
- Modified: `src/aeat/application/overview/test_calendar.py`
- Modified: `src/aeat/domain/calculations/registry/_schedules.py`
- Modified: `src/aeat/domain/deadlines/_engine.py`
- Created: `src/aeat/domain/calculations/registry/_applicability.py`
- Created: `src/aeat/domain/calculations/registry/applicability.py`
- Created: `src/aeat/domain/calculations/registry/test_modelo_applicability.py`
- Created: `src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py`
- Created: `src/aeat/domain/deadlines/taxpayer_model.py`
- Created: Modelo 202 filing schedule, deadline window, and application-link TOML files under the 2025-y-siguientes revision.

## Description

The completed cluster removes the autónomo-by-default assumption from
the overview path and routes filing, applicability, calculation
selection, and rate/bracket schedule references from the declared
taxpayer model. Registry-owned applicability rules now expose the core
per-entity and per-regime modelo set through a non-cyclic public
surface, while the overview compatibility module preserves the existing
application imports.

The Modelo 202 deadline registry now supplies legal-entity instalment
windows consumed by `DeadlineEngine`. The W03.S13 rate-schedule row was
closed from existing implementation evidence plus a registry-level
supplement proving natural-person IRPF bracket tables and legal-entity
IS rate dispatch are both registered and grounded.

W02.S08 adds explicit `tax_route`, `calculation_selections`, and
`rate_schedule_resolutions` payloads to `OverviewCalendar`. Rate
schedule rows carry `filing_year` and are resolved for every year in
the requested calendar range, so multi-year calendar output is no
longer ambiguous.

## Tests

Final W02.S08 gates passed:

- `uv run ruff check src/aeat/application/overview/__init__.py src/aeat/application/overview/test_calendar.py`
- `uv run pytest src/aeat/application/overview/test_calendar.py -q`
- `uv run pytest src/aeat/application/overview/test_calendar.py src/aeat/application/overview/test_applicability.py src/aeat/application/overview/test_explain.py src/aeat/application/overview/test_agenda.py src/aeat/application/overview/test_backlog.py src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py src/aeat/domain/calculations/registry/test_modelo_applicability.py src/aeat/domain/deadlines/test_engine.py -q`
- `uv run aeat app registry verify`
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-21-taxpayer-type-applicability-plan.md`
- `uv run vaultspec-core vault plan status .vault/plan/2026-05-21-taxpayer-type-applicability-plan.md --json`
- `uv run vaultspec-core vault plan query .vault/plan/2026-05-21-taxpayer-type-applicability-plan.md --open`

The mandatory W02.S08 code review passed with no findings after a
follow-up review confirmed the multi-year rate-schedule ambiguity was
resolved. Earlier W03.S11, W03.S12, and W03.S13 reviews were likewise
persisted in `.vault/audit/` and used to close their rows.
