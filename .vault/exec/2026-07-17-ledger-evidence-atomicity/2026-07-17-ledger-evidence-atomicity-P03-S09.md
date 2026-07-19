---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S09'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Prove attach remains the sole evidence mutation, invoice link is atomic and invoice-only, and link rejects every removed evidence grammar

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`

## Description

- Add `test_link_rejects_removed_evidence_id_grammar` (passing `--evidence-id` is an unknown-option refusal) and `test_link_requires_invoice_id` (a bare `link <tx>` refuses because `--invoice-id` is now required).
- Retarget `test_link_refuses_unknown_transaction_id` off the removed `--evidence-id` onto `--invoice-id`.
- Retain the instructive invoice-not-found proof (`test_link_refuses_operator_invoice_add_id_instructively`) proving a slim `invoice add` id is refused with the typed message routing to the evidence path.

## Outcome

- Proves `ledger link` is invoice-only, rejects every removed evidence grammar, and that attach remains the sole evidence mutation door (the generic-patch refusal is the S02 application-level proof). `test_ledger_link_check_verbs.py`: 11 passed (integration). Commit `aa99b74e47`.

## Notes

- Real Typer runner against an isolated profile-storage backend; no mocks.
