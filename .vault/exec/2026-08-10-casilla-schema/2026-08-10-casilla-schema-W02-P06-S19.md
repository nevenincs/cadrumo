---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:32a8e7f80f5803cdb60a4f6e03fca148ae08de2604fb4b83ef3efd75f9928465'
step_id: 'S19'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Project IVA ledger and confirmation blockers onto operator action classes

## Scope

- `src/cadrumo/application/ledger/_preflight.py`
- `src/cadrumo/application/ledger/__init__.py`
- `src/cadrumo/core/_confirmation_gate.py`
- `src/cadrumo/core/__init__.py`
- Direct preflight, confirmation, and future-period aggregation tests

## Description

- Declare one total immutable action projection for all native `IvaLedgerAggregationIssueReason` members on the ledger preflight path.
- Declare one total immutable core-to-core action projection beside `ConfirmationBlockReason`.
- Preserve every native reason beside its projected `OperatorActionAxis`, refuse missing or stale mapping keys at import, and publish both identities from their canonical facades.
- Delete the pre-existing checked-in enum mutation harness; retain real screen-emission, totality, facade-identity, and production aggregation behavior tests.

## Outcome

- All 22 IVA ledger issues and all five confirmation blockers project to typed operator action classes without aliases or fallback inference.
- A valid future Q3 row evaluated against Q2 retains native `OUTSIDE_PERIOD` and projects `REVIEW_ADVISORY`; it does not invent prior-period filing or ledger repair work.
- The application-ledger lazy facade carries matching runtime and `TYPE_CHECKING` ownership.
- Focused behavior lanes passed 54 tests; final exact review lane passed six tests. Ruff, strict BasedPyright, and diff-check are green.
- Formal review raised two MEDIUM findings over two rounds; both were corrected and the final verdict is PASS.

## Notes

- Fresh VaultSpec RAG located the two canonical owners and the accepted blocker-spine ADR fixed the placement and totality contract.
- The first review rejected `OUTSIDE_PERIOD -> FILE_PRIOR_PERIOD`; the second correctly rejected `IMPORT_LEDGER_DATA` because an out-of-window row may be valid. The final nonblocking advisory mapping follows actual consumer suppression.
- No fake, stub, mock, patch, monkeypatch, skip, xfail, compatibility alias, or mirrored business logic was introduced.
