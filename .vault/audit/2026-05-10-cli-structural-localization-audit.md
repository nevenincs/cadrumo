---
tags:
  - '#audit'
  - '#cli-structural-localization'
date: '2026-05-10'
modified: '2026-05-10'
related:
  - '[[2026-05-10-eliminate-user-cli-shim-adr]]'
  - '[[2026-05-10-eliminate-user-cli-shim-plan]]'
---

# Audit Finding: CLI Structural and Localization Regression
#audit #cli #i18n #ux-025

**Audit Date:** 2026-05-10
**AEAT Revision:** `07436143`
**Status:** OPEN

## 1. Localization Regressions (Missing `tr()`)

The following CLI `help` strings use plain string literals instead of the mandatory `tr()` locale system. This bypasses the localization pipeline and prevents translations for these messages.

| File | Line | Finding |
| :--- | :--- | :--- |
| `src/aeat/entrypoints/cli/_setup.py` | 190 | `help="Clear the persisted provider session..."` |
| `src/aeat/entrypoints/cli/registry.py` | 749 | `help="Surface live-parity oracle binding mismatches at startup."` |
| `src/aeat/entrypoints/cli/registry.py` | 766 | `help="Live parity catalogue environment to audit against: production / test_environment / both."` |

## 2. Architectural Violation: `user_cli.py` Shim

The module `src/aeat/application/user_cli.py` is identified as an architectural shim/shadow.

### Findings:
*   **Improper Placement:** Located in `src/aeat/application/`, but carries CLI-specific naming and state.
*   **Shadow State:** Manages `UserCliState` including active profiles and auth methods which are already partially handled or should be handled by the entrypoint layer or dedicated infrastructure adapters.
*   **Mandate Violation:** Violates the project mandate: *"we mandate no shims or shadows"*.
*   **Unwired Logic:** Contains significant logic for `LedgerReviewRecord` and `InvoiceReviewRecord` (Lines 117-151) that appears to be implementing "dark" workflow persistence not fully exposed or consistent with the primary domain models.

## 3. Unconnected/Dark CLI Subroutines

Mechanical check of `src/aeat/entrypoints/cli/` reveals the following subroutines implemented but unconnected to the root `app` in `src/aeat/entrypoints/cli/__init__.py`:

| Subpackage | Status | Implementation |
| :--- | :--- | :--- |
| `data/ledgers` | UNWIRED | Implements `inventory.py` and `movements`. |
| `deadlines` | UNWIRED | Implements `list`, `next`, `explain` for filing deadlines. |
| `browser` | UNWIRED | Implements `health` probes for Playwright. |
| `sanitize` | EMPTY | Contains only `__pycache__`. |
| `llm` | EMPTY | Contains only `__pycache__`. |

*   `_ledger.py`: Logic for complex splits (`LedgerSplit`) exists in `user_cli.py` and is referenced here, but the CLI surface for manual split entry is not fully exercised in current integration tapes.
*   `_invoice.py`: Annotation persistence via `update_invoice_review` is implementation-heavy in the application layer but lacks high-visibility wiring in the `aeat app` overview.

## 4. Recommended Hardening Rules

To prevent further regressions, the following rules must be enforced:

1.  **Type-Level Gating:** CLI `help` parameters must be typed as `Translatable` (from `aeat.core.i18n`). Plain `str` must be rejected by type-checkers (`ty`).
2.  **Shim Eradication:** `src/aeat/application/user_cli.py` must be refactored. Persistence logic should move to `aeat.adapters.persistence.workflow`, and naming must be decoupled from the CLI transport.
3.  **Mechanical tr() Check:** A CI step or pre-commit hook must grep for `help="` and `help='` in `src/aeat/entrypoints/cli/` to ensure no raw literals are introduced.
