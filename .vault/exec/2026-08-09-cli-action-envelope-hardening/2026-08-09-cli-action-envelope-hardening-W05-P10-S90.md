---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:10fe3ab2198f36eb251b61bd6702edab1f1717d7bbbc3ca1f20da0cb3c247d64'
step_id: 'S90'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate ledger CLI action producers and co-located renderers without independently authored command prose, including direct PurchaseInvoiceEvidenceInputError consumer migration in _ledger_llm_cli.py and _ledger_lifecycle_cli.py so S38 reader-unavailability verdicts reach the shared envelope intact.

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`
- `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py`

## Description

- Remove local `LLMClassifierError` catches that redeclared producer failures as CLI-authored prose.
- Remove the local `PurchaseInvoiceEvidenceInputError` string projection from the split consumer.
- Propagate typed ledger failures to the shared command boundary so canonical precondition verdicts and action envelopes remain intact.
- Preserve operational failures as their registered typed errors without classifying them as false precondition failures.

## Outcome

- Completed the immediate S38 consumer handoff in the two assigned ledger CLI modules.
- Confirmed no stale `PurchaseInvoiceEvidenceInputError`, `LLMClassifierError`, or `cli.ledger.classify.llm_failed` references remain in the assigned modules.
- Verified 21 ledger CLI integration behaviors, 14 shared action-resolution behaviors, and 5 producer distinction behaviors.
- Verified reader unavailability remains `PurchaseInvoiceEvidenceInputError` with its canonical terminal verdict, while an available-reader operation failure remains `LLMClassifierError`; both reach the shared CLI boundary without a local prose wrapper.
- Ruff check, Ruff format check, Python compilation, and diff whitespace validation pass for both assigned modules.
- S90 remains open because the wider ledger CLI migration is outside this handoff slice.

## Notes

- Focused basedpyright reports only the modules' pre-existing private shared-helper import diagnostics; the changed call sites introduce no new typing surface.
- Vault execution mapping and body-section checks complete successfully with unrelated pre-existing corpus warnings.
