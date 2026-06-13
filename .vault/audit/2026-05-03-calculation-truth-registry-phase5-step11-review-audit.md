---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step11-exec]]'
---

# `calculation-truth-registry` Code Review

Review result:

- Initial review found one coverage regression and one stale wording issue:
  - Generic `FilingValidator` behavior lost direct coverage when the static
    schemas were deleted.
  - `_testing_synthesize.py` still described real drafts as flowing through
    rulesets and formulas.
- Fixes applied:
  - Added non-model-specific in-test schema records covering schema-version
    mismatch, required missing, range violation, and formula divergence.
  - Cleaned the stale wording in `_testing_synthesize.py`.
- Follow-up review result: no findings.

Verification reviewed:

- ruff passed on `src\aeat\application\filing` and the deletion gates.
- ty passed on `src\aeat\application\filing` and the deletion gates.
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\application\filing`
  passed with 202 passed and 4 skipped.

Residual risk:

- Registry-backed production schema/provider behavior is still fail-closed
  until validated snapshots are introduced.
