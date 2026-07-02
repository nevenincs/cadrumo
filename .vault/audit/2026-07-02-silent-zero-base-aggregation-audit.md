---
tags:
  - '#audit'
  - '#silent-zero-base-aggregation'
date: '2026-07-02'
modified: '2026-07-02'
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
formally deferred to that future prorrata mechanism and must not be checked as
completed registry bindings.

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
record exists, but the plan checkbox remains pending because the plan file carried
pre-existing non-authored WIP before the step-check edit window.

### s14-code-review | low | no blocking findings in the real CLI M100 evidence change

The S14 review re-read the scoped diff after the test passed. The implementation
extends an existing real CLI source-mesh test rather than adding a parallel harness:
the test creates the work unit through the CLI, persists real ledger rows, calculates
Modelo 100 through the CLI, and now asserts all three plan-named casillas. No mocks,
stubs, skips, xfail markers, or tautological formula reimplementation were introduced.

## Recommendations

Leave S03/S04 open as ADR-deferred prorrata work. Check S06 only after the
non-authored plan-file WIP clears so `vaultspec-core vault plan step check` can run
without overwriting a peer edit. Do not declare this campaign closed: `vault plan
status` still reports open steps.
