# ADR: Eliminating `user_cli.py` Architectural Shim
#adr #cli #workflow #ux-025

**Status:** PROPOSED
**Date:** 2026-05-10
**AEAT Revision:** `07436143`

## Context

The module `src/aeat/application/user_cli.py` currently serves as a catch-all for "workflow state" required by the CLI, including:
- Active setup profile management.
- Local auth provider configuration and readiness status.
- Manual review annotations for ledger postings and invoices.
- "Last-built" pointers for tax declarations.

This module is identified as an architectural regression because:
1. It violates the "no shims or shadows" mandate.
2. It carries CLI-specific naming in the application layer.
3. It shadows logic that should be owned by domain-specific application services.
4. It implements "dark" logic (review records) not fully integrated into the primary data pipelines.

## Decision: Eradicate and Migrate

We will delete `src/aeat/application/user_cli.py` and migrate its functionality to the backend as follows:

### 1. Profile Management -> `aeat.application.profile`
- `ProfileRecord` and the profile-value normalization logic will move to `src/aeat/application/profile/`.
- Actions (`set_active_profile`, `set_profile_values`) will be integrated into the existing profile application service.
- This ensures `aeat setup profile` is powered by a first-class application service.

### 2. Auth Readiness -> `aeat.application.auth`
- `AuthState` will be refactored into a `LoginReadiness` model.
- The state will be managed as part of the unified workflow service, reflecting whether a session is configured and verified without shadowing the actual session storage.

### 3. Review Annotations -> `aeat.application.review`
- `LedgerReviewRecord`, `LedgerSplit`, and `InvoiceReviewRecord` will move to `src/aeat/application/review/`.
- These models represent the operator's manual categorization decisions (e.g., splitting a personal/business expense).
- This logic will be exposed to the CLI via a `ReviewService`.

### 4. Workflow State -> `aeat.application.workflow`
- `DeclarationPointer` and the root `UserCliState` (to be renamed to `WorkflowState`) will move to `src/aeat/application/workflow/`.
- This service will track the "operator's desk" state (active profile, last draft, current task).

### 5. Persistence Namespace
- The `UserCliStateRepository` will be renamed to `WorkflowStateRepository`.
- The storage namespace will change from `aeat.application.user_cli` to `aeat.workflow`.

## Consequences

- **CLI Purity**: The CLI entrypoints will remain thin transport layers, calling only into typed application services.
- **Zero Functionality Loss**: The migration is a 1:1 functional map, ensuring existing user profiles and reviews survive the transition.
- **Architectural Integrity**: Business logic is centralized in the backend, and shims are eliminated.
- **Type Safety**: All workflow state will be strictly typed and managed by the backend, facilitating the "translatable" gating rules for CLI output.
