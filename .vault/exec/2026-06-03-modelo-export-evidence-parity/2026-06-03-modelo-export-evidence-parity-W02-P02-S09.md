---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S09'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W02.P02.S09` step record

Scope: `W02.P02.S09` - Refuse exporting a ledger-derived revision that carries neither bundled evidence nor a resolvable reference.

## Description

- Add an export-specific evidence-missing refusal for ledger-derived revisions.
- Gate `export_modelo_revision` after revision load and before file emission.
- Register the new refusal in the stable error-code registry.
- Cover the helper and real export service refusal with verified calculation revisions.

## Outcome

Modelo export now refuses a ledger-derived revision when `source_transaction_ids` is non-empty and the revision carries neither bundled `ledger_filing_evidence` nor a `ledger_filing_snapshot` reference.

## Notes

`src/aeat/application/modelo/_export.py` had unrelated IVA-wallet worktree edits. The S09 commit stages only the evidence-gate hunks for that file, leaving unrelated edits in the shared worktree untouched.
