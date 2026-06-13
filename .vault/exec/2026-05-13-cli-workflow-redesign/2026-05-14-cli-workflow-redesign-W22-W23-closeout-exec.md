---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W22..W23'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` W22..W23 closeout

Closed plan rows: every row of `W22.P106..W22.P110` and
`W23.P111..W23.P115`, 60 plan rows total
(`S0631..S0660`, `S0661..S0690`).

## W22 — invoice domain decoupling

The legacy `aeat app invoice` mount is absent. Source-kind
taxonomy is locked in `BucketEventType`:
`PAYABLE_INVOICE_{CREATED,UPDATED,REMOVED}`,
`COLLECTIBLE_INVOICE_{CREATED,UPDATED,REMOVED}`,
`PURCHASE_INVOICE_EVIDENCE_{ATTACHED,REPLACED,DETACHED}`.

The `application/invoices/` package owns importing, linking, and
projection. The `domain/invoices/` package carries the typed
records.

The retired `aeat app invoice` legacy verbs are pinned by
`test_rejected_aliases_do_not_reach_apex_workflow_services`.

## W23 — ledger transaction management

The `aeat app ledger` Typer mount registers 16 canonical verbs
in `entrypoints/cli/_ledger.py`: `create`, `edit`, `classify`,
`allocate`, `attach`, `archive`, `stash`, `remove`, `reset`,
`export`, `list`, `read`, `status`, `track`, `import`,
`review`. Each delegates to `application/ledger/_actions`
canonical service.

Backend boundary tests
(`test_manual_ledger_registry_uses_accepted_command_vocabulary`,
`test_manual_ledger_import_and_review_boundaries_stay_backend_owned`,
`test_manual_ledger_help_rejects_legacy_vocabulary_across_subcommands`)
enforce the verb tree, the backend ownership of import + review
logic, and the rejection of legacy `set-ratio`, `unset-ratio`,
`split`, `sanitize`, `financial` vocabulary.

## Guards held

- No legacy `aeat app invoice` or `aeat financial` mount.
- No CLI-local ledger import / review logic.
- No metastate codification of removed surfaces beyond the
  rejected-aliases pin already present in
  `test_apex_workflow_verification.py`.
