---
tags:
  - '#plan'
  - '#eliminate-user-cli-shim'
date: '2026-05-10'
modified: '2026-05-10'
related:
  - '[[2026-05-10-eliminate-user-cli-shim-adr]]'
  - '[[2026-05-10-cli-structural-localization-audit]]'
  - '[[2026-05-07-user-profile-schema-research]]'
  - '[[2026-04-12-setup-wizard-research]]'
  - '[[2026-05-12-cli-design-research]]'
---

# Plan: Eliminate `user_cli.py` Architectural Shim
#plan #cli #workflow #ux-025

**Status:** DRAFT
**Owner:** Gemini CLI
**Date:** 2026-05-10
**Task:** Eradicate `src/aeat/application/user_cli.py` and migrate logic to backend.

## 1. Prerequisites
- [ ] Audit all imports of `aeat.application.user_cli` across the workspace.
- [ ] Ensure `src/aeat/application/review/` is ready to receive new models.

## 2. Phase 1: Review Logic Migration
- [ ] Create `src/aeat/application/review/_models.py` (if not exists) or update it.
- [ ] Move `LedgerSplit`, `LedgerReviewRecord`, and `InvoiceReviewRecord` from `user_cli.py` to `src/aeat/application/review/`.
- [ ] Move `WorkflowEvent` to `src/aeat/application/workflow/` as it's a shared event type.
- [ ] Update `src/aeat/application/review/__init__.py` to export these models.

## 3. Phase 2: Profile Logic Migration
- [ ] Move `ProfileRecord` and `_normalise_key` to `src/aeat/application/profile/`.
- [ ] Integrate `set_active_profile`, `set_profile_values`, and `clear_profile_values` into `src/aeat/application/profile/` services.
- [ ] Update `src/aeat/application/profile/__init__.py`.

## 4. Phase 3: Auth & Workflow State Migration
- [ ] Move `AuthState` to `src/aeat/application/auth/` (possibly rename to `AuthSessionReadiness`).
- [ ] Move `DeclarationPointer` and `UserCliState` to `src/aeat/application/workflow/`.
- [ ] Rename `UserCliState` to `WorkflowState`.
- [ ] Rename `UserCliStateRepository` to `WorkflowStateRepository`.
- [ ] Update the repository namespace from `aeat.application.user_cli` to `aeat.workflow`.
- [ ] Update `src/aeat/application/workflow/__init__.py`.

## 5. Phase 4: CLI Entrypoint Update
Update imports in the following files:
- [ ] `src/aeat/entrypoints/cli/_common.py`
- [ ] `src/aeat/entrypoints/cli/_declaration.py`
- [ ] `src/aeat/entrypoints/cli/_invoice.py`
- [ ] `src/aeat/entrypoints/cli/_ledger.py`
- [ ] `src/aeat/entrypoints/cli/_setup.py`
- [ ] `src/aeat/entrypoints/cli/test_cli_surface.py`
- [ ] `src/aeat/entrypoints/cli/test_user_cli_surface.py`

## 6. Phase 5: Implementation Audit & Localization Hardening
- [ ] Fix the regressed `help` strings identified in the audit (`_setup.py`, `registry.py`).
- [ ] Verify all `help` parameters in CLI now use `tr()`.
- [ ] (Optional) Propose type-gating for `Translatable` if not already enforced.

## 7. Phase 6: Final Cleanup
- [ ] Delete `src/aeat/application/user_cli.py`.
- [ ] Run full test suite: `uv run pytest tests`.
- [ ] Verify 100% green state (619+ tests).

## 8. Verification
- [ ] `aeat setup status` returns correct profile and auth status.
- [ ] `aeat app ledger list` (and related review commands) still persist annotations.
- [ ] Secure backend contains the migrated `aeat.workflow` namespace.
