---
tags:
  - "#adr"
  - "#filing-draft-engine"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-filing-draft-engine-research]]"
---
# ADR — Filing draft generation engine (#39)

Date: 2026-04-12
Status: Accepted
Branch: `feature/39-filing-draft-engine`

## Context

The project needs a single typed answer to "what does the system
actually produce?". Every upstream catalogue feeds into this
answer; without it, downstream issues (submission, AEAT round-trip,
per-modelo builders) have nothing concrete to integrate against.

## Decision

Introduce `aeat.application.filing` — a new subpackage that owns the typed
public API for building, validating, and inspecting `FilingDraft`
records.

### Pydantic v2 schema

All boundary-crossing records are strict pydantic v2 models with
`ConfigDict(strict=True, frozen=True, extra="forbid")`:

- `FilingDraftStatus` (`enum.StrEnum`): `DRAFT`, `VALIDATED`,
  `READY_TO_SUBMIT`, `SUBMITTED`, `ACKNOWLEDGED`, `REJECTED`,
  `AMENDED`, `CANCELLED`. This issue produces drafts only up to
  `READY_TO_SUBMIT`; the remaining states are reserved for the
  future submission engine and exist now so its callers can pin
  the enum without churn.
- `FilingValueKind` (`enum.StrEnum`): `LITERAL`, `COMPUTED`,
  `INHERITED`, `DEFAULT`, `EMPTY`.
- `FilingFindingSeverity` (`enum.StrEnum`): `ERROR`, `WARNING`,
  `INFO`.
- `FilingValue` (`BaseModel`): the typed value of one casilla,
  carrying its kind, provenance string, and structured
  `formula_trace`.
- `FilingValidationFinding` (`BaseModel`): the result of one
  validation rule firing, carrying severity, stable code,
  `Translatable` message, and a tuple of Manual práctico rule IDs.
- `FilingDraft` (`BaseModel`): the top-level draft, with
  content-addressed `draft_id`, status, values, findings, and
  trilingual-aware `notes`.

### Builder ABC

`FilingBuilder` is an abstract base class with a single
`build(period, profile, inputs) -> FilingDraft` method.
Implementations live under `src/aeat/application/filing/_builders/` and are
registered via a private `_BUILDER_REGISTRY` keyed by modelo
string ID. The PoC ships `Modelo130Builder` only.

### Validator

`FilingValidator` is a concrete class that applies cross-cutting
rules (deadline check via `DeadlineChecker` Protocol stub, profile
applicability, schema-version compatibility, missing required
casillas, out-of-range values, formula divergence). The validator
is invoked once by `build_draft` and again by `validate_draft`.

### Public functions

- `build_draft(modelo, period, profile, inputs)` — selects builder,
  runs it, runs validator, returns the frozen draft.
- `validate_draft(draft)` — re-runs the validator and returns a new
  draft with updated findings/status. The `draft_id` is preserved
  because re-validation does not change content.
- `iter_findings(draft, *, severity_at_least)` — generator over
  findings filtered by severity.

### Cross-module Protocols

`aeat.application.filing._protocols` declares Protocols for every upstream
collaborator (`ModeloIdentity`, `CasillaSchema`, `CasillaCollection`,
`CasillaSchemaProvider`, `DeadlineStatus`, `DeadlineChecker`). The
PoC ships hand-written concrete implementations under
`_builders/_modelo_130_schema.py` and the test doubles in
`test_filing.py`. Production wiring will replace these on rebase
once the upstream subpackages land.

### Errors

A small hierarchy under `aeat.core.errors.AeatError`:

- `FilingDraftError` — base for the subpackage.
- `FilingBuilderError` — builder selection / execution failure.
- `FilingValidationError` — raised when the caller asks for a
  strict-validate failure (`fail_on_warning=True` and any warning
  surfaced).
- `FilingComputationError` — raised by builders when a formula
  cannot be evaluated.

### CLI

A new `aeat.entrypoints.cli.filing` Typer sub-app wires four commands into the
root `aeat` CLI: `build`, `validate`, `show`, `list`. Drafts are
written as JSON files under `AEAT_DRAFTS_DIR`.

### Settings

Two additive settings on `aeat.core.config.Settings`:

- `aeat_drafts_dir: Path` — default `<PROJECT_ROOT>/var/drafts`.
- `aeat_draft_fail_on_warning: bool` — default `False`.

Both are documented in `env/.env.example`; the alignment test in
`tests/test_config.py` enforces parity.

## Consequences

- Downstream issues (per-modelo builders, submission engine,
  storage integration) inherit a stable, frozen API surface and
  can pin the enum/model imports today.
- The Protocol stubs for `aeat.domain.casillas`, `aeat.domain.schema`,
  `aeat.domain.deadlines`, `aeat.domain.modelos` create a small rebase cost when
  those subpackages land — explicitly accepted.
- The `FilingDraft.draft_id` is content-addressed and stable; the
  same `(modelo, period, profile, inputs)` tuple always produces
  the same id, which makes deduplication and idempotent retries
  trivial for the future submission engine.
- Drafts on disk under `var/drafts/` are an interim shape; the
  storage layer (#10) will absorb them later without changing the
  pydantic schema.

## Non-goals

- Submission to AEAT.
- Builders for modelos other than 130.
- A `FilingDraftSession` interactive editing surface.
- LLM-driven autocompletion of inputs.
