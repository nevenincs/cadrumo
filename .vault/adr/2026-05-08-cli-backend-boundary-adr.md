---
tags:
  - '#adr'
  - '#cli-backend-boundary'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-cli-backend-boundary-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---



# `cli-backend-boundary` adr: `CLI backend boundary` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The AEAT CLI has accumulated workflow, parsing, validation, persistence,
calculation, reconciliation, and reporting behavior that belongs in Python
backend services. This creates false confidence in CLI tests, hides missing
backend APIs, and lets the command surface become an application layer with
its own business rules.

The required architecture is that the CLI is a presentation and invocation
adapter only. It may bind command arguments, construct typed backend request
objects, call backend services, render backend result DTOs, and translate
typed backend errors into user-facing messages. It must not own tax,
financial, persistence, registry, deadline, import/export, or reconciliation
logic.

## Considerations

- The codebase already contains domain and application packages for ledgers,
  payable invoices, collectible invoices, purchase invoice evidence, filing,
  deadlines, profile, registry, and diagnostics.
- Several CLI modules currently duplicate or shadow backend concerns rather
  than exposing backend services.
- Tests that assert CLI-owned business behavior produce regression risk
  because they can pass while backend APIs remain incomplete.
- The user-facing CLI still needs strong behavior, but that behavior must be
  supplied by typed backend services and covered by backend contract tests.

## Constraints

- No legacy compatibility layer is required for CLI-owned business logic.
- Existing shared-worktree changes by other agents must remain intact.
- Work must proceed in small, reviewable waves with commits between major
  steps.
- Tests must not use tautological assertions, transient development state,
  phases, stamps, broad mocks, skipped checks, or false-positive existence
  checks.
- Missing backend behavior is in scope and must be implemented in backend
  services rather than worked around in the CLI.

## Implementation

The rollout will follow `2026-05-08-cli-backend-boundary-research` and
`2026-05-08-cli-backend-boundary-reference`. Every CLI business-logic finding
is assigned a row ID. Each row moves through audit, backend API implementation,
CLI simplification, backend contract tests, CLI wrapper tests, and code review.

The CLI will be reduced to these allowed responsibilities:

- Typer command and option declaration.
- Minimal syntactic option normalization needed to construct typed backend
  request objects.
- Invocation of backend command services.
- Rendering of backend result DTOs.
- Translation of typed backend exceptions into stable CLI diagnostics.

Backend services will own import/export round trips, profile schema behavior,
ledger financial transaction parsing, payable/collectible invoice parsing,
purchase invoice evidence parsing, matching, reconciliation, filing inputs,
deadline readiness, registry queries, inventory calculations, and diagnostics.

## Rationale

This decision makes missing backend APIs visible instead of allowing the CLI
to compensate with command-local logic. It also creates a sharper test
boundary: business behavior is tested through backend APIs, while CLI tests
verify command wiring, rendering, and error translation.

The research inventory shows repeated examples where CLI modules own domain
grammar, persistence flows, import parsing, reconciliation mutation, registry
selection, filing input coercion, and overview status aggregation. Keeping
that logic in the CLI would preserve the root regression. Moving it behind
typed backend services aligns the implementation with the centralized schema
and Pydantic rollout already in progress.

## Consequences

The near-term implementation cost is higher because backend gaps must be
filled instead of papered over in CLI modules. Some existing CLI tests must be
deleted or migrated because they currently pin the wrong ownership boundary.

The long-term result is a stricter architecture: CLI surfaces become thinner,
backend APIs become reusable by Python callers, and regression tests validate
real behavior rather than command-local mirrors of business rules.
