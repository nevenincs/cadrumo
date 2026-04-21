---
tags:
  - "#exec"
  - "#deadline-engine"
date: 2026-04-12
title: Filing-Deadline Computation Engine - Execution Log
related:
  - "[[2026-04-12-deadline-engine-research]]"
  - "[[2026-04-12-deadline-engine-adr]]"
  - "[[2026-04-12-deadline-engine-plan]]"
issue: wgergely/aeat#38
---

# execution log: filing-deadline computation engine

## summary

Implemented `aeat.deadlines` per the ADR and plan. The subpackage
exposes the public API listed in the issue (`AutonomoProfile`,
`IVARegime`, `ObligationStatus`, `FilingObligation`, `Schedule`,
`DeadlineEngine`, `applies_to`, `next_deadline`) plus a small
`CanonicalWindow` calendar surface and a `ModeloCatalogueLoader` /
`CorpusReader` Protocol pair for the in-flight upstream subpackages
(#6, #17). The CLI sub-app `aeat deadlines` is wired through the
existing typer root with three subcommands (`list`, `next`, `explain`).
Two additive Settings fields (`AEAT_DEFAULT_PROFILE_PATH`,
`AEAT_DEADLINE_DUE_SOON_DAYS`) are documented in `env/.env.example`
and the alignment test passes.

## artefacts produced

- `src/aeat/deadlines/__init__.py` - public re-exports + usage example
- `src/aeat/deadlines/_errors.py` - `DeadlineError`, `ProfileError`,
  `ScheduleComputationError`
- `src/aeat/deadlines/_protocols.py` - `ModeloIdentifier`,
  `ModeloCatalogueLoader`, `CorpusReader`
- `src/aeat/deadlines/_models.py` - strict pydantic v2 models for
  `AutonomoProfile`, `FilingObligation`, `Schedule`, plus the
  `IVARegime` and `ObligationStatus` enums
- `src/aeat/deadlines/_calendar.py` - `CanonicalWindow`, `PeriodKind`,
  the `CALENDAR` table for 2024-2027, citation constants, and
  `KNOWN_AUTONOMO_MODELOS`
- `src/aeat/deadlines/_applies.py` - per-modelo applicability rules
  with BOE / Manual práctico citations
- `src/aeat/deadlines/_engine.py` - `DeadlineEngine` and
  `next_deadline` (pure functions)
- `src/aeat/deadlines/test_models.py` - strict-validation, frozen,
  JSON round-trip
- `src/aeat/deadlines/test_calendar.py` - calendar invariants
- `src/aeat/deadlines/test_applies.py` - per-modelo truth tables
- `src/aeat/deadlines/test_engine.py` - membership, windows, status
  transitions, purity, JSON round-trip
- `src/aeat/cli/deadlines/__init__.py` - typer sub-app wiring
- `src/aeat/cli/deadlines/_helpers.py` - profile loading + in-process
  catalogue (real Protocol implementation, not a mock)
- `src/aeat/cli/deadlines/list.py` - `aeat deadlines list`
- `src/aeat/cli/deadlines/next.py` - `aeat deadlines next`
- `src/aeat/cli/deadlines/explain.py` - `aeat deadlines explain`
- `src/aeat/cli/deadlines/test_cli.py` - CliRunner smoke tests for all
  three commands
- `src/aeat/cli/__init__.py` - mount the new sub-app
- `src/aeat/config.py` - additive Settings fields
- `env/.env.example` - documented entries for the additive fields

## quality gates

- `uv run ruff check .` - all checks passed
- `uv run ruff format --check .` - formatted
- `uv run ty check src tests` - all checks passed
- `uv run pytest` - 278 passed, 1 skipped, 9 deselected (live)
- `uv run prek run --all-files` - all hooks passed

## sibling-branch territories left untouched

`pyproject.toml [tool.pytest]`, `tests/conftest.py`, `tests/README*`,
`src/aeat/models/`, `src/aeat/corpus/`, `src/aeat/manuals/`,
`src/aeat/portals/`, `src/aeat/auth/`, `src/aeat/schema/`,
`src/aeat/sync/`, `src/aeat/storage/` were not modified.
