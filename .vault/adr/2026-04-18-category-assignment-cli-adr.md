---
tags:
  - "#adr"
  - "#category-assignment"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-category-assignment-cli-research]]"
---

# category-assignment-cli-adr

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## status

Accepted

## context

GitHub Issue #253 requires Kent to be able to assign a spending category to a transaction using the CLI. This is a blocker for the Classification milestone.
The current `aeat financial txs classify` command only allows setting the high-level business classification (e.g., BUSINESS, PERSONAL, MIXED) and a business percentage. It lacks the ability to assign a specific spending category from the 39-category catalogue or provide a reason for the classification.

However, our research (`[[2026-04-18-category-assignment-cli-research]]`) confirms that the underlying `Transaction` domain model already supports `category_id` and `notes` fields. The `set_classification` service function simply needs to be updated to accept and persist these fields, and the CLI command needs new arguments to capture them from the user.

## decision

We will extend the `aeat financial txs classify` command to support two new optional flags:
- `--category`: Validated against the `SpendingCategory` enum (which represents the 39-category catalogue).
- `--reason`: A string to capture the user's reasoning for the classification, mapped to the `notes` field.

The `set_classification` service function in `src/aeat/domain/financial/transactions/_service.py` will be modified to accept these two optional arguments and apply them when creating the updated `Transaction` instance.

## consequences

**Positive:**
- Unblocks the Classification milestone (DP6).
- Reuses existing domain model fields (`category_id` and `notes`), avoiding database or schema migrations.
- Provides a seamless CLI experience for Kent to fully classify a transaction in one command.

**Negative:**
- The CLI command signature grows, but since the new flags are optional, it remains backward compatible for simpler classifications.

**Neutral:**
- Will require updating the unit tests in `src/aeat/domain/financial/transactions/test_cli.py` to ensure the new flags are properly parsed and persisted.
