---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S2304'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` `W84.P405.S2304`

Read the W84 supporting ADR set and established the bare `invoice` baseline before implementation.

- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Reviewed the Apex CLI workflow ADR source-kind taxonomy, per-modelo aggregation pipeline ADR, and invoice-domain-decoupling ADR. Baseline verification found bare `invoice` binding declarations only in Modelo 349 and confirmed the W84 aggregation collection note was stale because the Renta ledger aggregation tests collected successfully.

## Tests

Baseline commands used:

- `uv run --no-sync vaultspec-core vault plan query .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --wave W84 --open`
- `rg -n 'source = "invoice"' registry/aeat/modelos src/aeat/domain/calculations/registry src/aeat/application/aggregation`
- `uv run --no-sync pytest --collect-only -q src/aeat/application/aggregation`
