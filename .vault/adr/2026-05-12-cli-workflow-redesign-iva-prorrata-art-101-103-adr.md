---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-research]]"
  - "[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr]]"
---

# `cli-workflow-redesign` adr: `IVA prorrata arts 101-103` | (**status:** `accepted`)

> **PARTIALLY-SUPERSEDED 2026-05-19**: The module-path direction in this ADR is reversed: Spanish stems are authoritative for tax-domain identifiers and domain/vat migrates into domain/iva. The LIVA arts. 101-103 legal grounding, application-aggregation observation contract, the Modelo 303 and Modelo 390 binding-provider design, and the separation from app-ledger-ratios and domain/usage_ratios remain in force; the legal IVA prorrata substrate lives under domain/iva rather than domain/vat.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.


## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The project has proportional expense usage ratios, but it does not implement
legal IVA prorrata. Mixed taxable/exempt activity needs a distinct VAT
substrate grounded in LIVA arts. 101-103.

## Considerations

IVA prorrata affects Modelo 303 and Modelo 390 deduction calculations. It is
not the same as operational business-personal allocation or proportional
expense usage.

## Constraints

Do not reuse `app ledger ratios`, `domain/usage_ratios`, or an
`app ledger prorrata` persistence shape. Do not translate usage ratios into
prorrata through a shim.

## Implementation

Create a legal IVA prorrata substrate under `domain/vat`. Application
aggregation emits prorrata observations for Modelo 303 and Modelo 390 binding
providers. Profile/config stores regime axes and accepted percentages where
needed, while calculation remains in the VAT substrate and aggregation layer.

## Rationale

Legal prorrata is a VAT calculation rule, not a ledger allocation convenience.
Separating it keeps ledger ratios useful for evidence classification without
turning them into legal deduction machinery.

## Consequences

Modelo 303 and 390 gain a proper prorrata input path. Ledger ratio code remains
limited to proportional expense/business usage. Tests must distinguish usage
ratio examples from legal prorrata examples.
