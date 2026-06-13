---
step_id: S240
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S240

**Add single-source-of-truth tests for `CLASSIFIED_BY_MANUAL` to `test_external_constants.py`.**

## Files touched

- `src/aeat/core/test_external_constants.py` — added six tests in a new `S238/S239/S240` section:
  - `test_classified_by_manual_value` — value equals `"manual"`.
  - `test_classified_by_manual_is_final_str` — type is `str`.
  - `test_application_ledger_imports_classified_by_manual_from_core` — public surface identity check.
  - `test_application_ledger_models_does_not_define_classified_by_manual_locally` — `_models` imports from core.
  - `test_domain_transactions_service_imports_classified_by_manual_from_core` — domain service imports from core.
  - `test_no_local_classified_by_manual_shadow_in_application_or_domain` — AST scan for re-definition assignments.

## Test design

The AST scan uses name-fragment matching (`classified_by`, `manual_classified`) on assignment targets, not a broad string-literal scan, to avoid false positives from the word `"manual"` in unrelated contexts (registry schemas, manual corpus paths, SourceFormat.MANUAL).

## Outcome

135 tests pass. All six new tests pass.
