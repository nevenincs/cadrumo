---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave4-step1-exec]]'
---



# `calculation-truth-registry` `Wave 4` `Modelo 123 reconciliation boundary`

Added Modelo 123 reconciliation coverage through the registry-gated
justificante comparison surface.

- Modified: `src/aeat/application/filing/reconciliation/test_reconcile.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The reconciliation suite now includes a Modelo 123 draft built through the
registry filing helper and a justificante record whose payable total matches
the registry-declared total casilla for the active revision.

The test exercises the public `reconcile` boundary. It proves that the payable
total is projected from the registry verification expectation instead of a
Python-side modelo branch or local reconciliation table.

## Tests

- `uv run ruff check src\aeat\application\filing\reconciliation\test_reconcile.py`
- `uv run ty check src\aeat\application\filing\reconciliation\test_reconcile.py`
- `uv run pytest src\aeat\application\filing\reconciliation\test_reconcile.py -q`
