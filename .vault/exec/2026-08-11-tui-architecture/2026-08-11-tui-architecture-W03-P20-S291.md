---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:40bd0461f12c877bfed2a962faf94802ce2c4517cee988a4ae2d6d3b438113b4'
step_id: 'S291'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Decide how a period-level ledger preflight issue reaches the workspace, since the producing issue admits a period sentinel alongside a transaction id while the workspace ledger issue type accepts a transaction id alone, leaving a period-scoped readiness problem with no representable arm: rule whether the workspace type gains the period arm or the issue is otherwise carried, and prove a period-level issue is never dropped nor forced into a fabricated transaction identity; amend the governing registry-api-gate decision record in the same change

## Scope

- `the amended 2026-08-24-tui-registry-api-gate-adr`
- `src/cadrumo/application/modelo/workspace_models.py ledger issue type`
- `src/cadrumo/application/ledger/preflight.py`
- `and focused period-scoped ledger issue tests`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_models.py` (commit `c03f834da4`: `ModeloWorkspaceLedgerIssueSubjectV1` discriminated union replacing the bare `transaction_id` field on `ModeloWorkspaceLedgerIssueV1`)
- `M` `src/cadrumo/application/modelo/tests/test_workspace_models.py` (commit `c03f834da4`: `test_workspace_ledger_issue_subject_distinguishes_transaction_from_period`)
- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md` (S291 amendment)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_models.py` -> `pass` (7 pre-existing unrelated diagnostics at lines 546/551/690, confirmed against HEAD)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_models.py -m integration -q` -> `pass` (30 passed, 1 pre-existing unrelated failure)

## Notes

Decided and built directly rather than proposing options: `LedgerPreflightIssue.transaction_id: TransactionId | Literal["__period__"]`
(`application/ledger/preflight.py:120`) is a closed two-arm sentinel with an
exact existing Workspace precedent for the fix shape -- S284's
`ModeloWorkspaceRecordLabelV1` discriminated union
(`ModeloWorkspaceLocalizedTextV1 | ModeloWorkspaceTechnicalLabelV1`), which
represents a similarly-shaped "this is not what it looks like" case as
itself rather than coercing it. Applied the same shape:
`ModeloWorkspaceLedgerIssueSubjectV1 = ModeloWorkspaceLedgerTransactionSubjectV1
| ModeloWorkspaceLedgerPeriodSubjectV1` (discriminated on `kind`), replacing
`ModeloWorkspaceLedgerIssueV1.transaction_id: TransactionId`. A period-level
issue (currently only `_unsupported_period_issue`, fired for a period with
no date span) is now represented as itself -- never dropped (a silent
under-declaration on exactly the axis an operator consults before filing)
and never pinned to a fabricated transaction id. No production consumer of
`ModeloWorkspaceLedgerIssueV1` exists yet (the readiness pass-through this
type feeds is not yet built), so this landed as a clean model-only change
with no fallout to sweep.
