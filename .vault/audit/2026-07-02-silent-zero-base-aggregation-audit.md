---
tags:
  - '#audit'
  - '#silent-zero-base-aggregation'
date: '2026-07-02'
modified: '2026-07-04'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

# `silent-zero-base-aggregation` audit: `Wave 1 D9 close-blocker audit`

## Scope

Wave 1 D9 close-blocker pass over the silent-zero plan status on 2026-07-02.
The pass reconciled the already-landed M390 predicate work, rechecked the remaining
open steps against the ADR and live tests, and scoped shared-worktree WIP before any
test edits. This audit is not a closure honesty review because the campaign is not
structurally complete.

2026-07-02 refresh: `uv run --no-sync vaultspec-core vault plan status
2026-06-19-silent-zero-base-aggregation-plan --json` reports 15 of 18 steps
complete, `next_open_step` = `W01.P02.S03`, and `exec_missing_ids` = `[]`.

2026-07-04 refresh: the same plan status reports 16 of 18 steps complete,
`next_open_step` = `W01.P02.S03`, and `exec_missing_ids` = `[]`; S06 is now
checked at HEAD.

## Findings

### m390-predicate-reconciled | low | S16 was implemented but unchecked

The M390 reconciliation predicate work was already present in commits `4e52feba3`
and `cac1f165f`. This pass added the S16 exec record and checked S16 through the
plan CLI. Focused verification passed:
`uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_390_registry.py src/aeat/application/modelo/tests/test_verification_m390_reconciliation.py`
reported 23 passed; full output is in `_scratch-wave1-d9/m390-reconciliation-tests.log`.

### prorrata-volume-steps-deferred | medium | S03 and S04 are superseded by the ADR mechanism decision

S03 and S04 remain unchecked by design. The plan text and ADR both record that
per-period prorrata volume bindings would be a wrong regulated mechanism for mixed
traders; the faithful mechanism is a cross-period prorrata model. These steps are
formally deferred to the named cross-period prorrata mechanism follow-up:
provisional-percentage carry plus Q4 regularisation over full-year volumes. They must
not be checked as completed registry bindings.

### real-cli-e2e-tests-reconciled | medium | S06 and S14 now have true CLI evidence

The codebase contains live application-service coverage for M303/M390 and M100 annual
ledger paths. A later S14 pass found that the existing real CLI M100 test already
proved `0171` and `0224` through `aeat app modelo work calculate`; the pass added
the missing `0180` assertion, reran the focused integration test green, and checked
S14 with a dedicated exec record.

The S06 follow-up added a real `aeat app quickfile` integration path for Modelo 303
2026 1T. The fixture seeds a real active profile, persisted ledger transactions,
linked purchase-invoice evidence, and a neutral IVA wallet decision, then invokes the
public quickfile chain without manual prorrata input. Verification passed:
`uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_app_quickfile.py::test_quickfile_m303_fully_taxable_ledger_reaches_granted_boe_without_prorrata_input`
reported 1 passed, and the full quickfile module reported 4 passed. The S06 exec
record exists, and the plan checkbox is now checked at HEAD.

### s14-code-review | low | no blocking findings in the real CLI M100 evidence change

The S14 review re-read the scoped diff after the test passed. The implementation
extends an existing real CLI source-mesh test rather than adding a parallel harness:
the test creates the work unit through the CLI, persists real ledger rows, calculates
Modelo 100 through the CLI, and now asserts all three plan-named casillas. No mocks,
stubs, skips, xfail markers, or tautological formula reimplementation were introduced.

## Fresh-Context Honesty Review

Reviewed the campaign as newly inherited, using the current plan status, the ADR's
prorrata mechanism decision, the exec-record inventory, the focused CLI evidence, and
the shared-worktree WIP checks as the authority. Findings:

### close-s03-s04 | medium | prorrata volume rows are an honest carry-forward, not incomplete implementation

`W01.P02.S03` and `W01.P02.S04` remain unchecked because the ADR rejects the
per-period volume binding shape as a regulated-mechanism error. The named follow-up is
the cross-period prorrata mechanism: provisional-percentage carry plus Q4
regularisation over full-year volumes. No bounded registry binding should be landed or
checked for these two rows in this campaign.

### close-s06 | low | S06 implementation is complete and checked

`W01.P02.S06` now has a dedicated exec record and real CLI verification through
`aeat app quickfile` for Modelo 303 2026 1T without manual prorrata input. The plan
row is checked at HEAD. No S06 follow-up remains.

## Closure Decision

For Wave 1 D9 purposes, this campaign's remaining tail is honestly drained: completed
rows have matching exec records, and the only open rows (`S03`/`S04`) are formally
deferred to a named cross-period prorrata mechanism. The vault plan remains open by
design because those deferred rows are intentionally unchecked; no missing exec alert
remains.

## Recommendations

Leave S03/S04 open as ADR-deferred cross-period prorrata work. Do not declare this
campaign closed: `vault plan status` still reports open steps by design for the
deferred prorrata rows.
