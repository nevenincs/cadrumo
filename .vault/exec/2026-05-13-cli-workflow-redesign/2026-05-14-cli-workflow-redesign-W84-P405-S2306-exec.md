---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S2306'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` `W84.P405.S2306`

Completed the application retenciones aggregation slice for Modelos 111, 115, 123, 180, 190, and 193.

- Modified: `src/aeat/application/aggregation/_retenciones.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `src/aeat/application/aggregation/test_retenciones.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Baseline verification found the pure retenciones aggregators already present for all six modelos, with tests, but source-kind validation only rejected bare `invoice`. The implementation now enforces the four canonical source kinds exactly: `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`.

Retenciones rollups now carry `source_kind` and aggregate by source-kind cohort, preventing different canonical source streams from being silently merged into one perceptor/scheme row. Retenciones aggregation types and functions are exported from `aeat.application.aggregation`, and the implementation note now describes 123, 180, 190, and 193 as implemented rather than future work.

## Tests

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_retenciones.py`
- `uv run --no-sync pytest --collect-only -q src/aeat/application/aggregation` collected 144 tests
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json`
