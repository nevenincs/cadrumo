---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S2316'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` `W84.P407.S2316`

Added typed registry rejection for bare `invoice` source kinds naming all four canonical alternatives.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`

## Description

Schema validation rejects TOML/model-load payloads that declare `source = "invoice"`. Registry validation keeps an equivalent guard for mutated in-memory definitions, with both paths naming `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`.

## Tests

Covered by `test_binding_schema_rejects_bare_invoice_source_kind_with_canonical_alternatives` and `test_validator_rejects_bare_invoice_source_kind_with_canonical_alternatives`.
