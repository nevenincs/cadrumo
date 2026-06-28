---
tags:
  - "#audit"
  - "#deadline-engine"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-deadline-engine-research]]"
  - "[[2026-04-12-deadline-engine-adr]]"
  - "[[2026-04-12-deadline-engine-plan]]"
---

# `deadline-engine` Code Review

Mandatory code review for issue wgergely/aeat#38 conducted on
2026-04-12 at the close of the vaultspec-execute cycle. The reviewer
audited every file modified or added by the feature branch
`feature/38-deadline-engine` against the project mandates (CLAUDE.md,
pydantic-mandate, src-layout-mandate, branch-naming, sibling-branch
territories) and the ADR / plan checklists.

## scope of review

Files added under `src/aeat/domain/deadlines/`, `src/aeat/entrypoints/cli/deadlines/`,
`.vault/{research,adr,plan,exec,audit}/`, plus the additive edits to
`src/aeat/entrypoints/cli/__init__.py`, `src/aeat/config.py`, and
`env/.env.example`. Sibling-branch territories
(`pyproject.toml [tool.pytest]`, `tests/conftest.py`,
`src/aeat/{models,corpus,manuals,portals,auth,schema,sync,storage}/`)
were verified to be untouched.

## findings

### TRUTH-TABLE-001 | INFO | applies_to truth tables sourced from research note citations only

Every per-modelo rule in `_applies.py` carries the BOE / Manual
práctico citation key in its docstring, and the citation is propagated
to the canonical window in `_calendar.py` and from there to every
emitted `FilingObligation.boe_references` tuple. The truth tables in
`test_applies.py` parametrise over the documented profile-flag
combinations from the research note. No invented rules.

### PYDANTIC-001 | INFO | strict pydantic v2 on every boundary type

`AutonomoProfile`, `FilingObligation`, `Schedule`, and `CanonicalWindow`
all use `model_config = ConfigDict(strict=True, frozen=True,
extra="forbid")`. Closed enumerations (`IVARegime`, `ObligationStatus`,
`PeriodKind`) are `enum.StrEnum`. No bare `dict[str, Any]` in any
public signature or persisted payload. The only `Any` usages are in
`__get_pydantic_core_schema__` (pydantic plumbing) and the
`source_type` parameter that pydantic itself types as `Any`. The
`CorpusReader.load_year_overrides` Protocol returns
`tuple[CanonicalWindow, ...]`, not `tuple[Any, ...]`.

### DATACLASS-001 | LOW | internal `_Rule` dataclass is non-boundary

`_applies._Rule` is a `@dataclass(frozen=True, slots=True)` used
exclusively as the value type of the internal `_RULES: dict[str, _Rule]`
table. It is never exported, never serialised, never crosses a public
boundary, never persisted. Per CLAUDE.md ("Use Enums for closed
catalogues, Pydantic models for wire/config, and dataclasses for
internal values"), this is the documented allowed use of dataclasses.
Verdict: compliant. No action.

### PURITY-001 | INFO | engine is a pure function

`DeadlineEngine.compute` performs no I/O after construction. It reads
from the catalogue Protocol's `is_known`, the optional corpus
Protocol's `load_year_overrides`, the in-code calendar tuple, and the
applies-to predicate table. It never mutates the input profile or the
catalogue. The test `TestEnginePurity::test_compute_does_not_mutate_profile`
asserts the profile is byte-for-byte equal before and after `compute`.
The test
`TestEnginePurity::test_compute_is_deterministic_modulo_generated_at`
asserts identical `(profile, year, today)` triples produce equal
obligations. The `today` argument defaults to `date.today()` at call
time only - the engine itself reads no global state.

### ERRORS-001 | INFO | error hierarchy rooted at AeatError

`DeadlineError`, `ProfileError`, and `ScheduleComputationError` all
inherit (transitively) from `aeat.core.errors.AeatError`. No stdlib
exceptions cross the public API of `aeat.domain.deadlines`. The CLI raises
`typer.BadParameter` for missing-argument cases, which is the standard
typer convention and never propagates as a domain error.

### LOGGING-001 | INFO | logging via aeat.core.logging.get_logger only

`_engine.py` uses `aeat.core.logging.get_logger(__name__)`. No bare
`logging.getLogger`, no `print`, no stdout writes from the engine
itself. The CLI uses `rich.console.Console` for user-facing output,
which is the documented convention from the existing
`aeat.entrypoints.cli.sync` sub-app.

### PUBLIC-API-001 | INFO | callers import only from aeat.domain.deadlines

Every internal module is `_`-prefixed (`_models`, `_engine`,
`_calendar`, `_applies`, `_protocols`, `_errors`). The public surface
is the closed `__all__` list in `aeat.domain.deadlines.__init__`. The CLI
sub-app imports only from `aeat.domain.deadlines`, never from any
underscore-prefixed internal module.

### DOCSTRINGS-001 | INFO | Google-style docstrings + type hints on every public symbol

Every public class, method, and function in `aeat.domain.deadlines` has a
Google-style docstring with `Args`, `Returns`, and `Raises` sections
where applicable. Type annotations are exhaustive on every public
signature.

### SIBLING-001 | INFO | sibling-branch territories left untouched

`git status --porcelain` shows the only modified files outside the new
subpackage are `src/aeat/entrypoints/cli/__init__.py` (additive sub-app mount),
`src/aeat/config.py` (additive Settings fields), and
`env/.env.example` (additive entries). `.gitignore` carried a
pre-existing modification from the worktree bootstrap. No files in
`src/aeat/{models,corpus,manuals,portals,auth,schema,sync,storage}/`,
`pyproject.toml [tool.pytest]`, or `tests/conftest.py` were modified.

### SETTINGS-001 | INFO | settings + .env.example aligned

`AEAT_DEFAULT_PROFILE_PATH` and `AEAT_DEADLINE_DUE_SOON_DAYS` are
defined in `aeat.core.config.Settings` with documented defaults and
documented in `env/.env.example`. The alignment test
`tests/test_config.py::TestEnvExampleAlignment` passes for both
fields.

### TESTS-001 | INFO | unit tests cover the required surfaces

`test_models.py` covers strict-validation, frozen, JSON round-trip.
`test_calendar.py` covers calendar invariants. `test_applies.py`
covers the truth tables for every modelo. `test_engine.py` covers
membership for the documented profile combinations, status
transitions across all four engine-produced statuses (`OVERDUE`,
`DUE_TODAY`, `DUE_SOON`, `UPCOMING`), `next_deadline` edge cases,
purity, and JSON round-trip on a full schedule. `test_cli.py` covers
the three CLI commands with a CliRunner. Every test carries
`pytestmark = pytest.mark.unit` (no live tests in this issue). No
mocks, patches, fakes, or stubs anywhere - the only Protocol
implementation is a real `_Catalogue` class with concrete methods.

### GATES-001 | INFO | lint, typecheck, tests, hooks all green

- `uv run ruff check .` - all checks passed
- `uv run ruff format --check .` - formatted
- `uv run ty check src tests` - all checks passed
- `uv run pytest` - 278 passed, 1 skipped, 9 deselected (live)
- `uv run prek run --all-files` - all hooks passed

## verdict

**APPROVED.** The implementation satisfies every constraint listed in
the issue, the ADR, the plan, and the project mandates. No `CRITICAL`
or `HIGH` findings. The single `LOW` finding (`DATACLASS-001`) is the
documented allowed use of an internal-value dataclass and requires no
action.
