---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]"
---



# `cli-workflow-redesign` adr: `domain harvest VAT classification` | (**status:** `accepted`)

> **PARTIALLY-SUPERSEDED 2026-05-19**: The Value-Added Tax direction in this ADR is reversed: Spanish stems are authoritative for tax-domain identifiers, VATClassification and VATClassificationCriteria consolidate into IvaInvoiceClassification, and domain/vat/_classification.py migrates into domain/iva/_classification.py. The CLI verb app-ledger-classify, the application wrapper aeat.application.ledger.classify_ledger_transaction, the JSON output contract, the persistence boundary, and the rejected-shapes list remain in force; only the classification symbol names and module path rename per the canonical rename ledger.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.


## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

`app ledger classify` is a ledger verb that must write classification through
transaction services.

The VAT classifier at `aeat.domain.vat._classification.classify_vat` is a
deterministic domain resolver. It maps `VATClassificationCriteria` to
`VATClassification(category, rate, requires_reverse_charge, matched_rule_id,
notes)` and performs no persistence.

Existing transaction classification persists business classification state,
percentage, category, notes, provenance, confidence, and history. The retired
financial transaction classify path must not be restored.

## Considerations

The live `app ledger` command surface has import, review, and edit, but no
classify command.

OSS/IOSS classification belongs to Modelo 369 under `app modelo`. IVA prorrata
is a separate concern.

`classify_vat` can enrich ledger classification output, but it is not the
ledger persistence boundary.

## Constraints

- No financial transaction classify surface is revived.
- No standalone `vat classify`, `app vat classify`, `app modelo classify`, or
  `app ledger vat classify` surface is introduced.
- The CLI does not call `set_classification` or `classify_vat` directly.
- No wrapper bypasses ledger persistence.
- OSS/IOSS and IVA prorrata remain separate domains.
- No compatibility shims are added.

## Implementation

Add `aeat.application.ledger.classify_ledger_transaction(...)` as the
application wrapper for ledger classification.

The wrapper:

- load the ledger transaction
- apply business classification through `set_classification`
- optionally normalize supplied VAT axes into `VATClassificationCriteria`
- call `classify_vat` only when VAT criteria are supplied
- persist classification through the catalogue
- return a structured classification result

Add `aeat app ledger classify TRANSACTION_ID ...` as the CLI consumer of this
wrapper.

Business classification mode accepts `--as
BUSINESS|PERSONAL|MIXED|PROCESSED_UNCLASSIFIED|SKIPPED_BY_RULE|FAILED_VALIDATION`,
`--pct`, `--category`, `--reason`, and `--confidence`.

VAT classification mode accepts explicit VAT criteria flags. Those flags
normalize into `VATClassificationCriteria`; derived VAT classification appears
in output, while persistence still flows through the wrapper.

The JSON output contract is:

- `operation`: `ledger.classification.set`
- `transaction_id`
- `business_classification`
- `business_pct`
- `category_id`
- `classified_by`
- `confidence`
- `reason`
- `vat_classification`
- `event_id`
- `bucket_id`
- `changed`

When present, `vat_classification` contains `category`, `rate`,
`requires_reverse_charge`, `matched_rule_id`, and `notes`.

The emitted event is `ledger.classification.set`.

## Rationale

Ledger classification has one application entrypoint for both business
classification and optional VAT-derived classification output. Keeping the VAT
classifier pure preserves the existing domain boundary while still exposing its
decision as part of ledger classification.

Separating this from OSS/IOSS and prorrata prevents legal/regime concepts from
being hidden inside a transaction classification command.

## Consequences

Ledger classification has one application entrypoint for both business
classification and optional VAT-derived classification output.

The VAT classifier remains pure domain logic and is not promoted into a
persistence API.

The CLI shape keeps ledger classification separate from Modelo 369 OSS/IOSS and
from IVA prorrata.

Rejected shapes:

- reviving financial transaction classify
- `aeat vat classify`
- `app vat classify`
- `app modelo classify`
- `app ledger vat classify`
- direct CLI calls to `classify_vat`
- wrappers that bypass persistence
- conflating ledger classification with OSS/IOSS
- prorrata language in this workflow
- compatibility shims
