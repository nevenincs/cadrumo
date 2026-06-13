---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
---



# `cli-workflow-redesign` adr: `app modelo bindings shape` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The CLI workflow redesign needs a locked app modelo binding surface for
required binding discovery, override preview, and calculation. Current
`_modelo.py` exposes a registry introspection command named `bindings`, but not
the target sub-app `list` and `preview` commands.

The phantom `data require/readiness` surface also needs a precise home. It must
not become a separate root or app family.

## Considerations

The app-modelo-shape and modelo lifecycle decisions require app modelo to own
modelo-scoped readiness and calculation workflows. Declaration binding behavior
parses `--binding` only as `KEY=Decimal` and injects values before
`build_draft`; `build_draft` then separates casilla inputs, calculation binding
inputs, and persisted filing binding values. Registry binding queries expose
static metadata but not readiness state.

UX-012 supplier flag closure is represented as declaration calculate
`--binding` with direct Decimal input. In the redesigned app modelo flow,
supplier flag closure is an explicit binding override shared by bindings
preview and calculate. Source-derived readiness still needs backend aggregation
and preflight support.

Implementation mandate: aggregate filing inputs produce modelo readiness facts
instead of returning an empty object outside Modelo 100.

## Constraints

- No `inputs` command family is introduced.
- `app declaration` does not survive as an operator surface.
- Root `filing`, `submit`, `presentation`, standalone `preflight`, and modelo
  support `help` surfaces are rejected.
- Mutating inventory does not move under `app modelo`.
- No shims or aliases are provided for rejected or old shapes.
- Output is emitted through `_emit`.
- `bindings list` and `bindings preview` are read-only and emit no bucket
  events.

## Implementation

Lock the app modelo bindings grammar as:

```text
aeat app modelo bindings list --modelo M --year YYYY --period P [--missing]
aeat app modelo bindings preview --modelo M --year YYYY --period P [--binding KEY=VALUE]
aeat app modelo calculate WORK_UNIT_ID | --modelo M --year YYYY --period P [--binding KEY=VALUE]
```

`bindings list` reports required and available binding keys for the
modelo/year/period. With `--missing`, it filters to unresolved required keys.

`bindings preview` resolves temporary `--binding` overrides and does not mutate
state. Overrides preserve scalar, list, and mapping values instead of
collapsing all input into Decimal-only bindings.

`calculate --binding` uses the same explicit binding override model as
`bindings preview`. Work-unit calculation and direct modelo/year/period
calculation share the same binding relationship.

The phantom `data require/readiness` family resolves to:

```text
aeat app modelo bindings list --modelo X --year YYYY --period P --missing
```

Missing binding failures are reported as domain-language readiness output, not
raw binding errors. Readiness output identifies the unresolved requirement as
one of:

```text
bucket
ledger source
profile fact
prior filed revision
live observation
casilla
waiver
blocking finding
```

Missing binding errors include a canonical next-command pointer derived from
the readiness category. Unknown binding keys fail with a suggestion list
sourced from the registry's binding catalogue for the active modelo / year /
period.

Calculate lifecycle events are handled by calculate/revision ADRs. Filing
records are handled by the filing-record ADR.

## Rationale

Bindings are the correct surface for modelo readiness because they describe the
inputs a modelo calculation requires and where those values come from. A
separate `data require` family would duplicate readiness behavior and hide the
connection to calculation.

Using the same override model for `bindings preview` and `calculate` lets the
operator inspect a temporary binding set before creating a calculation
revision. Keeping `list` and `preview` read-only prevents readiness inspection
from becoming a hidden mutation.

## Consequences

The app modelo surface becomes the single user-facing place for modelo binding
readiness discovery and temporary override preview.

Declaration-era Decimal-only binding parsing is replaced or bypassed for app
modelo binding overrides so scalar, list, and mapping values survive
resolution.

Registry binding metadata is not sufficient for readiness. Backend aggregation
or preflight work is still required for source-derived readiness, including
supplier flag closure.

Existing phantom `data require/readiness` references point to
`app modelo bindings list --modelo X --year YYYY --period P --missing`.

Raw missing binding errors are converted into readiness output with
fix-oriented domain language.

## 2026-05-14 amendment — test-user audit finding P1 #7 (list semantics)

Audit observation: `aeat app modelo bindings list` requires `--modelo`,
`--year`, and `--period`. With mandatory selectors it is a query, not a
list. A user reaching the `list` verb cannot discover the available
`--modelo` codes without first running `aeat app modelo list` to learn
what shape `--modelo` accepts.

Rule (this ADR scope; cross-cutting rule lives in the apex amendment):

- The `list` verb under `aeat app modelo bindings` MUST default to the
  unfiltered set: all configured bindings for the active profile/bucket.
  `--modelo`, `--year`, `--period`, and `--missing` MUST be optional
  refining filters, not gating selectors.
- When `--modelo` is supplied, the CLI MUST validate the value against
  the registry-derived enum of supported modelo codes and refuse unknown
  values with a typed validation error that lists the accepted set.
- `aeat app modelo bindings list --help` MUST surface the accepted
  `--modelo` enum (either inline in the help text or via a Typer choice).
- The query verb for "show me only the missing bindings for one modelo"
  remains expressible by supplying the optional filters. No separate
  `query` verb is introduced.

Acceptance criteria:

- `aeat app modelo bindings list` with no flags returns every binding for
  the active profile.
- `aeat app modelo bindings list --modelo BOGUS` refuses with a
  validation error that lists accepted codes.
- The accepted `--modelo` choices are derived from the registry, not
  hardcoded in the CLI.
