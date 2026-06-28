---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bank-provider-expansion-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr]]"
  - "[[2026-05-15-cli-workflow-redesign-audit]]"
---

# `cli-workflow-redesign` adr: `bank provider expansion` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Ledger ingestion does not cover several common Spanish bank export formats.
The redesign needs a provider-expansion path that improves coverage without
adding provider-specific CLI roots or live bank scraping.

## Considerations

Provider adapters are input parsers for ledger transactions. They belong behind
`app ledger import`/`ingest`, where source files become bucket-scoped ledger
facts.

## Constraints

Do not implement PSD2 or live scraping. Do not accept unsupported CSV files
heuristically. Do not add provider-specific CLI roots. Do not shim unknown bank
files into supported providers.

## Implementation

Add inbound adapters for ING, Sabadell, Openbank, Bankinter, and Triodos. Each
adapter declares supported file types, layout signatures, currency behavior,
and required fixture coverage.

Unsupported files fail closed with actionable provider/layout errors.

## Rationale

Explicit adapters make ledger import predictable and testable. Provider logic
stays in inbound parsing, while the CLI remains a stable ledger import surface.

## Consequences

Bank coverage expands without changing command topology. Tests must use real
or sanitized provider-shaped fixtures and must not pass through unsupported
heuristic imports.

## 2026-05-15 amendment - shipped catalogue ratification

The 2026-05-15 ground-truth audit verified that the original
Implementation list (ING, Sabadell, Openbank, Bankinter, Triodos) was
aspirational. The actual shipped CSV layouts under
`src/aeat/adapters/inbound/financial/providers/_csv.py` are:

- BBVA
- Santander
- CaixaBank
- Revolut
- N26 (also exposed via the dedicated `PdfN26Provider` for N26 PDF
  statements)

The W27 plan rows describe templated backend / shadow-removal /
de-shim / verification / thin-CLI work that did happen, just for a
different bank set than the ADR's original Implementation paragraph
named. Rather than uncheck plan rows or open a new wave to add the
five originally-named banks, this amendment ratifies the shipped
catalogue as the operator-facing set.

The Implementation list above is therefore superseded by the shipped
catalogue. ING / Sabadell / Openbank / Bankinter / Triodos remain
candidates for a future capacity wave if operator demand materialises;
they are not blocking R-rows on the apex §12 ledger. The status
remains `accepted` because the underlying decision (provider adapters
behind `app ledger import`, no PSD2 / live scraping, fail-closed on
unsupported files) is preserved by the shipped catalogue.

The bank-provider-expansion plan rows S0781-S0810 stay `[x]` per the
2026-05-15 audit verdict.
