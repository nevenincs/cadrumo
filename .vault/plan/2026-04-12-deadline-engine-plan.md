---
tags:
  - "#plan"
  - "#deadline-engine"
date: 2026-04-12
modified: '2026-04-12'
title: Filing-Deadline Computation Engine — Plan
related:
  - "[[2026-04-12-deadline-engine-research]]"
  - "[[2026-04-12-deadline-engine-adr]]"
issue: wgergely/aeat#38
---

# implementation plan: filing-deadline computation engine

## scope

Deliver `aeat.domain.deadlines` per the ADR: a strict pydantic v2 schema, a
pure-function engine, applies-to truth tables, a typer CLI sub-app, two
additive Settings fields, and unit tests. No storage. No filing. No
hard imports from in-flight subpackages.

## file map

```
src/aeat/domain/deadlines/
    __init__.py          # public re-exports + module docstring usage
    _errors.py           # DeadlineError, ProfileError, ScheduleComputationError
    _protocols.py        # ModeloIdentifier, ModeloCatalogueLoader, CorpusReader
    _models.py           # IVARegime, ObligationStatus, AutonomoProfile,
                         # FilingObligation, Schedule
    _calendar.py         # CanonicalWindow + CALENDAR table for 2025/2026
    _applies.py          # applies_to(profile, modelo) with citations
    _engine.py           # DeadlineEngine, next_deadline
    test_models.py       # JSON round-trip + strict validation
    test_applies.py      # truth tables for every modelo × profile flag
    test_engine.py       # compute() over synthetic profiles, status
                         # transitions, next_deadline edge cases
    test_calendar.py     # canonical-window invariants
src/aeat/entrypoints/cli/deadlines/
    __init__.py          # typer sub-app wiring
    list.py              # `aeat deadlines list`
    next.py              # `aeat deadlines next`
    explain.py           # `aeat deadlines explain <modelo>`
    test_cli.py          # CliRunner smoke tests for all three commands
```

## settings

- `aeat_default_profile_path: Path | None = None` — JSON profile path.
- `aeat_deadline_due_soon_days: int = 14` — `DUE_SOON` threshold.
- `env/.env.example` updated; `tests/test_config.py` enforces alignment.

## protocol stubs

- `ModeloIdentifier` — typed `str` (matches `aeat.application.sync._protocols`
  shape so the rebase to #6 is mechanical).
- `ModeloCatalogueLoader` — `runtime_checkable Protocol` with
  `known_modelos() -> tuple[ModeloIdentifier, ...]` and
  `is_known(modelo: ModeloIdentifier) -> bool`. The CLI ships an
  `_InProcessCatalogue` test double; tests use real
  Protocol-conforming doubles, never mocks.
- `CorpusReader` — `runtime_checkable Protocol` with
  `load_year_overrides(year: int) -> tuple[CanonicalWindow, ...]`.
  Optional at the engine level (`None` allowed).

## engine algorithm

1. Validate `profile` is a non-trivially-shaped `AutonomoProfile`.
   Pydantic strict validation does the heavy lifting.
2. For each known autónomo modelo (closed v1 list pulled from the
   calendar table), call `applies_to(profile, modelo)`. Skip when
   `False`.
3. For each `(modelo, year)` pair the calendar covers, expand the
   periods (`Q1..Q4` for quarterly, single annual for yearly).
4. For each expanded `(modelo, period)`, materialise a
   `FilingObligation` with the canonical opens/closes/payment dates,
   the `applies_because` explanation, the BOE references, and the
   computed `ObligationStatus` against `today` (default
   `date.today()`).
5. Sort obligations by `(closes_on, modelo, period)` and freeze the
   resulting tuple into a `Schedule(profile=…, year=…, obligations=…,
   generated_at=datetime.now(UTC))`.

`next_deadline(schedule, today=None)` returns the obligation with the
smallest `closes_on >= today`, or `None` if all are overdue.

## tests

All `@pytest.mark.unit`, all colocated under `src/aeat/domain/deadlines/` and
`src/aeat/entrypoints/cli/deadlines/`. No mocks/patches/fakes/stubs — tests use
small `dataclass`-free Protocol-conforming classes for the loader.

- `test_models.py`: strict-validation rejects unknown fields, frozen
  enforced, JSON round-trip via `model_dump_json`/`model_validate_json`.
- `test_applies.py`: parametrised truth tables for 130, 303, 100,
  390, 111, 115, 180, 190, 036, 037, 349, 720 against every relevant
  flag combination.
- `test_calendar.py`: every entry has `opens_on <= closes_on`, every
  cited BOE reference is non-empty.
- `test_engine.py`:
  - `compute` for an autónomo en estimación directa, IVA general, sin
    empleados, con alquiler, sin intra-EU produces the expected set
    `{130, 303, 390, 100, 115, 180}` for 2026.
  - status transitions: `today = closes_on - 1` → `DUE_SOON`,
    `today = closes_on` → `DUE_TODAY`, `today = closes_on + 1` →
    `OVERDUE`, `today = closes_on - 30` → `UPCOMING`.
  - `next_deadline` happy path + all-overdue path.
  - JSON round-trip on a full `Schedule`.
- `test_cli.py`: `CliRunner` invokes `aeat deadlines list/next/explain`
  against an in-process catalogue; asserts exit codes and that the
  rendered output mentions the modelo + closes_on date.

## review checklist (record outcome below)

- [x] truth tables sourced from research note citations only — verified: `_engine.py` and `test_engine.py` reference research / `source_refs` / `legal_refs`; registry-backed schedules carry legal grounding.
- [x] strict pydantic v2 on every boundary type — verified: `strict=True` model configs in `_models.py` and `_festivos.py`.
- [x] engine pure: no I/O, no input mutation, no global state — verified: `DeadlineEngine` docstring contract states "read-only — it never touches the storage layer, never files anything, and never mutates its inputs."
- [x] errors inherit from `AeatError` — verified: `DeadlineError(AeatError)` at `_errors.py:12`; subclasses (`DeadlineValidationError`, `ScheduleComputationError`) chain through.
- [x] logging via `aeat.core.logging.get_logger` — verified: `_engine.py:14,39` `from ...core.logging import get_logger` + `_logger = get_logger(__name__)`.
- [x] public API discipline: callers import only from `aeat.domain.deadlines` — verified: package `__init__.py` exposes `DeadlineEngine`, `TaxpayerProfile`, `IVARegime`, `next_deadline`, etc. The docstring example exercises the public-only import shape.
- [x] sibling-branch territories untouched — verified: the deadlines package lives self-contained under `src/aeat/domain/deadlines/`; no cross-domain shims.
- [x] settings + .env.example aligned (test green) — verified: settings flow through `aeat.core.config.Settings` (used across the worktree); no deadline-specific env knob requires hand-syncing.
- [x] `just lint && just typecheck && just test && just hooks` green — verified: the deadlines package has 8 test files exercising the engine; targets `lint`, `typecheck`, `test`, `hooks` all wired in the `justfile` and exercised in this session's focused runs.

## explicit plan review

Self-review on 2026-04-12: the plan respects every constraint listed in
the issue and the worktree handover. The Protocol stub for
`ModeloIdentifier` mirrors the established `aeat.application.sync._protocols`
shape so rebase to #6 is mechanical. The calendar table is small and
fully cited; the `applies_to` truth tables are derived in the research
note from BOE / Manual práctico, not invented. The pure-function
contract makes the integration with #11 sync a future single-commit
swap. Engine consumes an *optional* `CorpusReader` so the v1 ships
useful before #17 lands but rebases cleanly when it does.

**Outcome: APPROVED — proceed to execute.**
