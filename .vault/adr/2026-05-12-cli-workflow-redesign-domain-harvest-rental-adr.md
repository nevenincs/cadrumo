---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-rental-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
---



# `cli-workflow-redesign` adr: `domain harvest rental` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The rental domain has real backend capability but is not productized through the
application layer or CLI.

Apex marks Modelo 100 as calculation-ready, while also identifying a rental
aggregation backend gap. The missing pieces are an application wrapper and
complete Modelo 100 rental binding support.

The domain rental layer exposes records, repositories, aggregate
calculation, tier resolution, expense rollup, and amortization directly. CLI
code must not call domain repositories directly.

## Considerations

The Modelo 100 binding path supports first-slice Renta ledger
expense aggregation through declaration-era `_aggregate_filing_inputs`, with
registry support limited to `ledger_renta_expense_aggregation`. Rental register
aggregation needs its own binding source/provider.

Rental SQL tables follow the bucket-linked contract.

Article 22-24 tiers are derived facts. The CLI should record source facts and
show tier explanation/readiness, not let users select tax outcomes.

## Constraints

- No root-level `aeat rental ...` command is introduced.
- No rental-specific `anexo-c` command is introduced.
- No direct CLI calls to rental domain repositories are allowed.
- No compatibility shims are carried forward.
- Rental records and events are bucket-linked before the CLI is productized.
- Modelo calculation events remain modelo-owned.

## Implementation

Add `aeat.application.rental` before exposing rental CLI behavior.

The application wrapper provides:

- `list/get/create/update/dispose finca`
- `list/create/update/terminate contracts`
- `record/list income`
- `record/list expense`
- `recompute_amortization`
- `compute_rental_aggregates_for_year`
- `resolve/preview_modelo100_rental_bindings`

Place rental register mutation and inspection under the app ledger namespace:

```text
aeat app ledger rental finca ...
aeat app ledger rental contract ...
aeat app ledger rental income ...
aeat app ledger rental expense ...
aeat app ledger rental amortization ...
```

Expose Modelo 100 rental readiness through existing modelo binding commands:

```text
aeat app modelo bindings list --modelo 100 --year YYYY --period annual
aeat app modelo bindings preview --modelo 100 --year YYYY --period annual
```

Modelo 100 calculation consumes the resulting binding path through:

```text
aeat app modelo calculate
```

Add a new binding source/provider named `rental_register_aggregation`. Do not
overload `ledger_renta_expense_aggregation` and do not keep rental aggregation
hidden behind declaration-era `_aggregate_filing_inputs`.

Article 22-24 tiers are derived by the domain/application output. The CLI
records source facts only and shows tier explanation, readiness, and missing
facts.

Application mutations emit:

- `rental.finca.created`
- `rental.finca.updated`
- `rental.finca.disposed`
- `rental.contract.created`
- `rental.contract.updated`
- `rental.contract.terminated`
- `rental.income.recorded`
- `rental.expense.recorded`
- `rental.amortization.recomputed`

Binding preview is read-only and emits no event.

## Rationale

Rental facts are source facts and register state, so mutation and inspection
belong under the ledger source-data workflow. Modelo 100 should consume those
facts through bindings rather than through a rental-specific calculation
surface.

An application wrapper gives CLI code a bucket-aware, event-aware API and
prevents direct repository calls from becoming the integration boundary.

Keeping tier selection derived preserves legal reasoning: users provide facts,
the backend explains the applicable tier.

## Consequences

Rental becomes a first-class app workflow without exposing domain repositories
directly to CLI code.

Modelo 100 rental integration becomes explicit through
`rental_register_aggregation`, preserving the existing ledger expense
aggregation path for its current purpose.

The CLI remains source-fact driven. Tier selection is derived and explainable
rather than user-selected.

Rejected shapes:

- root-level `aeat rental ...`
- rental-specific `anexo-c` commands
- direct CLI calls to rental domain repositories
- old shims for rental command compatibility
- hidden declaration aggregate reuse for rental register bindings
- user-selected art. 23.2 tier flags
