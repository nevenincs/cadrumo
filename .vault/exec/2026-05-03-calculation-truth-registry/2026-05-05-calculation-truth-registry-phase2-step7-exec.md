---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step7-review-audit]]'
---



# `calculation-truth-registry` `Phase 2` `Step 7`

Gated filing reconciliation on registry-backed draft snapshots and registry
verification expectations.

- Modified: `src/aeat/application/filing/reconciliation/_reconcile.py`
- Modified: `src/aeat/application/filing/reconciliation/test_reconcile.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step7-review.md`

## Description

The reconciliation use case now requires a registry-backed provider. Before any
AEAT justificante metadata is compared, the draft schema version must match the
active registry snapshot and the registry snapshot must declare verification
expectations.

The reconciliation tests now build Modelo 130 drafts through registry-backed
public helpers and parse checked-in justificante fixtures. Local filing value
and schema construction was removed from the tests.

## Tests

`uv run pytest src\aeat\application\filing\reconciliation\test_reconcile.py -q`

`uv run ruff check src\aeat\application\filing\reconciliation\_reconcile.py src\aeat\application\filing\reconciliation\test_reconcile.py`

`uv run ty check src\aeat\application\filing\reconciliation\_reconcile.py src\aeat\application\filing\reconciliation\test_reconcile.py`
