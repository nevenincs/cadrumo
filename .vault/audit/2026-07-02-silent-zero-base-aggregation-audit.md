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

### real-cli-e2e-tests-blocked | medium | S06 and S14 still need true CLI evidence

The codebase contains live application-service coverage for M303/M390 and M100 annual
ledger paths, but this pass did not find a true real-CLI test satisfying the exact S06
and S14 wording. The target test surface `src/aeat/application/modelo/tests/` already
has substantial non-authored WIP, and the dispatch forbids interleaving new tests into
dirty peer-owned files. S06 and S14 remain unchecked and formally deferred until the
test surface is peer-clean and the owner can add real CLI evidence for the M303 `.boe`
prorrata case and the M100 0171 / 0180 / 0224 ledger case.

## Recommendations

Leave S03/S04 open as ADR-deferred prorrata work. Resume S06/S14 only after the
application-modelo test surface is clean enough to add real CLI tests without carrying
peer WIP. Do not declare this campaign closed: `vault plan status` still reports open
steps.
