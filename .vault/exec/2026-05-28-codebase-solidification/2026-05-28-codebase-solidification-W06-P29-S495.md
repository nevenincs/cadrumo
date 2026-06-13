---
step_id: S495
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S495

**Step**: aggregate inventory test asserting zero survivors of each pattern in production.

## Outcome

`src/aeat/test_w06_p29_constants_inventory.py` with 5 real-behavior tests:
- `test_no_bare_ledger_transaction_literals` — zero `"ledger_transaction"` outside enum defs
- `test_no_bare_xls_extension_literals` — zero `".xls"` outside canonical definition
- `test_no_duplicate_sede_body_encoding_definition` — no duplicate `SEDE_BODY_ENCODING = "latin-1"`
- `test_no_bare_production_oracle_environment_bypass` — no `environment="production"` kwarg
- `test_no_bare_invoice_source_kind_literals` — no `== "invoice"` / `source="invoice"` comparisons

All 5 pass. Test is on comment-skipping scan to avoid false positives from docstrings.

## Files

- `src/aeat/test_w06_p29_constants_inventory.py`

## Commit

5b45dd58c
