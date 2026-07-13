---
tags:
  - '#plan'
  - '#eliminate-user-cli-shim'
date: '2026-05-10'
modified: '2026-07-12'
related:
  - '[[2026-05-10-eliminate-user-cli-shim-adr]]'
  - '[[2026-05-10-cli-structural-localization-audit]]'
  - '[[2026-05-07-user-profile-schema-research]]'
  - '[[2026-04-12-setup-wizard-research]]'
  - '[[2026-05-12-cli-design-research]]'
  - '[[2026-07-12-eliminate-user-cli-shim-audit]]'
---
# Plan: Eliminate `user_cli.py` Architectural Shim

> **Reconciled 2026-07-12 â€” delivered, not active.** `application/user_cli.py` was removed and its responsibilities were migrated into the canonical workflow and profile boundaries. The draftâ€™s retired package paths and `setup` spellings are not current work. Evidence is recorded in `2026-07-12-eliminate-user-cli-shim-audit`.#plan #cli #workflow #ux-025

**Status:** DRAFT
**Owner:** Gemini CLI
**Date:** 2026-05-10
**Task:** Eradicate `src/aeat/application/user_cli.py` and migrate logic to backend.

## 1. Prerequisites
- [x] Audit all imports of `aeat.application.user_cli` across the workspace.
- [x] Ensure `src/aeat/application/review/` is ready to receive new models.

## 2. Phase 1: Review Logic Migration
- [x] Create `src/aeat/application/review/_models.py` (if not exists) or update it.
- [x] Move `LedgerSplit`, `LedgerReviewRecord`, and `InvoiceReviewRecord` from `user_cli.py` to `src/aeat/application/review/`.
- [x] Move `WorkflowEvent` to `src/aeat/application/workflow/` as it's a shared event type.
- [x] Update `src/aeat/application/review/__init__.py` to export these models.

## 3. Phase 2: Profile Logic Migration
- [x] Move `ProfileRecord` and `_normalise_key` to `src/aeat/application/profile/`.
- [x] Integrate `set_active_profile`, `set_profile_values`, and `clear_profile_values` into `src/aeat/application/profile/` services.
- [x] Update `src/aeat/application/profile/__init__.py`.

## 4. Phase 3: Auth & Workflow State Migration
- [x] Move `AuthState` to `src/aeat/application/auth/` (possibly rename to `AuthSessionReadiness`).
- [x] Move `DeclarationPointer` and `UserCliState` to `src/aeat/application/workflow/`.
- [x] Rename `UserCliState` to `WorkflowState`.
- [x] Rename `UserCliStateRepository` to `WorkflowStateRepository`.
- [x] Update the repository namespace from `aeat.application.user_cli` to `aeat.workflow`.
- [x] Update `src/aeat/application/workflow/__init__.py`.

## 5. Phase 4: CLI Entrypoint Update
Update imports in the following files:
- [x] `src/aeat/entrypoints/cli/_common.py`
- [x] `src/aeat/entrypoints/cli/_declaration.py`
- [x] `src/aeat/entrypoints/cli/_invoice.py`
- [x] `src/aeat/entrypoints/cli/_ledger.py`
- [x] `src/aeat/entrypoints/cli/_setup.py`
- [x] `src/aeat/entrypoints/cli/test_cli_surface.py`
- [x] `src/aeat/entrypoints/cli/test_user_cli_surface.py`

## 6. Phase 5: Implementation Audit & Localization Hardening
- [x] Fix the regressed `help` strings identified in the audit (`_setup.py`, `registry.py`).
- [x] Verify all `help` parameters in CLI now use `tr()`.
- [x] (Optional) Propose type-gating for `Translatable` if not already enforced.

## 7. Phase 6: Final Cleanup
- [x] Delete `src/aeat/application/user_cli.py`.
- [x] Run full test suite: `uv run pytest tests`.
- [x] Verify 100% green state (619+ tests).

## 8. Verification
- [x] `aeat setup status` returns correct profile and auth status.
- [x] `aeat app ledger list` (and related review commands) still persist annotations.
- [x] Secure backend contains the migrated `aeat.workflow` namespace.
