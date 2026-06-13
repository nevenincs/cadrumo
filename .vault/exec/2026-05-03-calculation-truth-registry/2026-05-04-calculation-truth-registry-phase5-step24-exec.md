---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `phase5` `step24`

Removed the authority scanner test and tightened the filing runtime schema
provider around validated registry snapshots.

- Deleted: `tests/import_contract/test_runtime_authority_hard_cut.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/application/filing/test_schema_completeness.py`
- Modified: `src/aeat/application/filing/test_import.py`
- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The import-contract scanner that asserted removed module names was deleted.
Tests now remain focused on runtime behaviour: committed registry data loads,
snapshots validate, filing subviews expose closure data, imports build
registry-backed draft scaffolds, and warnings are emitted as stable message
keys.

`build_runtime_schema_provider` now builds snapshot-backed filing subviews for
the selected modelo revision. The subview exposes revision, legal/source
closure, extraction profiles, verification expectations, export layouts,
application links, and deadline windows while preserving the existing
`get_collection` validator protocol.

## Tests

- `uv run pytest src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/domain/rental tests/import_contract/domain/rental -q`
- `uv run ruff check src/aeat/application/filing/runtime.py src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/domain/rental tests/import_contract/domain/rental`
- `uv run ty check src/aeat/application/filing/runtime.py src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/domain/rental tests/import_contract/domain/rental`
