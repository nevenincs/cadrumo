---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# Phase 5 Step 12 Execution

Disabled legacy complementaria amendment construction:

- Replaced `build_complementaria` with a fail-closed boundary that rejects
  amendment construction until validated registry snapshots own the amendment
  anchors.
- Removed Python-owned amendment kind resolution, rectificativa cutoffs,
  liability anchor selection, delta calculation, and persistence from the
  complementaria builder.
- Retained persisted amendment read/list surfaces so existing audit evidence
  can still be inspected.
- Added deletion gates proving the removed helper names and modelo-specific
  anchors do not return to the implementation.

Rationale:

- Complementaria and rectificativa behavior is legal filing truth, not an
  application-local formula table.
- The codebase must not decide amendment type, liability movement, or
  modelo-specific correction rules from hardcoded Python branches.

Verification:

- `uv run --no-sync ruff check src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\application\filing`
- `rg` confirmed the removed anchors only appear in deletion-gate assertions
  and the fail-closed message.

Result: ruff passed, ty passed, and the focused pytest slice passed with
203 passed and 4 skipped.

Residual risk:

- Wrapper-level persisted-record round trips for `load_amendment` and
  `list_amendments` remain only indirectly covered by repository tests.
- Production amendment construction remains intentionally unavailable until
  validated registry snapshots provide the legal amendment basis.
