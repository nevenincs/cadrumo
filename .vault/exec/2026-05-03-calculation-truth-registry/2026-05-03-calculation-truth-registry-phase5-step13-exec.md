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

# Phase 5 Step 13 Execution

Removed filing-runtime modelo applicability derivation:

- Deleted the `_SUPPORTED_FILING_MODELOS` tuple from
  `src/aeat/application/filing/runtime.py`.
- Removed the filing runtime dependency on deadline-domain `applies_to`.
- Changed `filing_profile_from_autonomo` so it copies taxpayer identity only
  and returns an empty `applicable_modelos` tuple.
- Added a deletion gate proving supported filing modelos are not derived from
  Python runtime constants or deadline-engine projection.

Rationale:

- Filing obligations and supported modelo applicability are legal registry
  truth. They must not be derived from an application-local tuple or a separate
  deadline-domain projection.
- Runtime profile loading can preserve identity metadata, but it cannot answer
  filing obligation questions until validated registry data exists.

Verification:

- `uv run --no-sync ruff check src\aeat\application\filing\runtime.py tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\application\filing\runtime.py tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\application\filing\test_schema_completeness.py src\aeat\application\filing\test_import.py src\aeat\application\filing\test_filing.py`
- `rg` confirmed removed runtime anchors only appear in deletion-gate
  assertions.

Result: ruff passed, ty passed, and the focused pytest slice passed with
59 passed.

Residual risk:

- Registry-backed obligation/modelo applicability is still absent, so runtime
  profile loading intentionally cannot determine filing obligations.
