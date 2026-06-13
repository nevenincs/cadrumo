---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-inventory-placement-research]]"
  - "[[2026-04-30-inventory-management-cli-design-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` adr: `inventory placement and execution` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The inventory CLI is implemented under `aeat data ledgers inventory`, but the
workflow redesign permits only two roots: `aeat config` and `aeat app`. The
inventory feature needs a new canonical placement that preserves the financial
ledger meaning without keeping an illegal `data` root.

## Considerations

Inventory is operational ledger evidence. It supports activity/year inventory
ledgers, movement recording, valuation methods, and valuation previews used by
ledger and modelo workflows. It is not configuration or bucket maintenance.

The older inventory ADR remains useful for command verbs and hardening gates,
but its root placement conflicts with the accepted root contract.

## Constraints

No `aeat data` root is allowed. No hidden `data` shim, forwarding alias, or
compatibility command survives. Inventory must not move under `config` or
`app modelo`. Every persisted inventory mutation is bucket-scoped and emits a
bucket event. Output uses root `--format json|text` and `_emit`.

## Implementation

Move retained inventory command placement to `aeat app ledger inventory`:

Implementation mandate: harvest the inventory Typer implementation into
`app ledger inventory`, rewrite command copy from `aeat data ledgers
inventory`, and remove the `data` path without a shim.

```text
aeat app ledger inventory list [--format json|text]
aeat app ledger inventory create ACTIVIDAD --year YEAR --valuation-method METHOD [--opening-stock AMOUNT] [--format json|text]
aeat app ledger inventory movement add --actividad ID --year YEAR --movement-id ID --date DATE --kind KIND --quantity QTY [--unit-cost AMOUNT] [--taxable-base AMOUNT] [--vat-rate RATE] [--format json|text]
aeat app ledger inventory valuation preview --actividad ID --year YEAR [--format json|text]
```

Update command strings, help text, schema identifiers, tests, and operator
documentation that encode `data ledgers inventory`.

`list` and `valuation preview` are read-only and emit no bucket event. `create`
and `movement add` are persisted mutations and emit bucket events using the
`ledger.inventory.*` namespace.

## Rationale

`aeat app ledger inventory` preserves the meaning of inventory as financial
evidence preparation while obeying the two-root contract. `config` remains
reserved for profile, bucket, auth, and diagnostics. `app modelo` may consume
inventory-derived facts, but it does not own the mutable inventory ledger.

## Consequences

The `data` root is retired, not aliased. Inventory output names and schema
identifiers stop advertising `data ledgers inventory`. Existing implementation
can be harvested, but command registration, rendering, events, tests, and help
copy must be rewritten to the `app ledger inventory` path.
