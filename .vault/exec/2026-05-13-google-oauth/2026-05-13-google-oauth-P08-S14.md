---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S14'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-07-14-google-oauth-audit]]"
---

# `P08.S14` — write a forbidden-import test asserting no `sync pull --workspace-edits` (or any Sheets-pull) verb is registered under `aeat config google sync` in v1

## Scope

- `the test introspects the Typer command tree and fails if any matching command exists`
- `defends ADR-7's deferral invariant against future drift`
- `tests/import_contract/google/test_no_sheets_pull_verb.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# write a forbidden-import test asserting no `sync pull --workspace-edits` (or any Sheets-pull) verb is registered under `aeat config google sync` in v1

## Scope

- `the test introspects the Typer command tree and fails if any matching command exists`
- `defends ADR-7's deferral invariant against future drift`
- `tests/import_contract/google/test_no_sheets_pull_verb.py`

## Description

- Reconcile `P08.S14` against the accepted July architecture and current code.
- Ground the disposition with Vaultspec RAG and exact source and CLI evidence.
- Record the result in the related reconciliation audit before closing the row.

## Outcome

Superseded by the accepted bidirectional calculation-Sheets decision and the current `calc pull` command.

## Notes

No implementation was added. The former prohibition is retired and must not be reintroduced.
