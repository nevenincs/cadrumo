---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:e4f2ab5cb11981be1be705f00f38cef1c024caa581b2389386b6a374c97b74c4'
step_id: 'S03'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove the stale user-profile censo-sync adapter ignore entry

## Scope

- `.importlinter`

## Description

- Ground the Step with `vaultspec-rag search "user profile censo sync stale adapter import-linter ignore" --type code`.
- Inspect `_censo_sync.py`, its facade loading, live callers, deferred repository route, lazy-import policy declarations, and the ignore ledger.
- Remove only `cadrumo.application.user_profile._censo_sync -> cadrumo.adapters.**`.
- Run all five contracts uncached and classify every remaining planned boundary without fixing it.

## Outcome

The stale censo-sync waiver is gone. The live service retains its read-only affected-area ratio and provenance-tag surface, and no source, import, caller, contract, wildcard, or other waiver changed.

The uncached graph analyzed 3,421 files and 16,152 dependencies. Four contracts were kept: the calculations-registry contract, both domain contracts, and the full layered contract. The sole broken contract was `Core must not import outer layers`, reporting only the helper-mediated chain from `cadrumo.core.tests.test_isolation_fixture_state_root_coverage` through `cadrumo.tests.secure_sql`; S04 owns that exact route.

S05, S07, and S10 remain open but are not newly exposed broken-contract findings. S05 narrows the still-matching `diagnostics_run_health -> adapters.**` pin. S07 removes the optional public IRNR resolver door left after S06 eliminated the adapter edge. S10 widens the OSS/IOSS injected invoice annotations while retaining its accepted default composition path and standing `_oss_ioss` construction waiver. None was altered here.

## Notes

The semantic query returned the general architecture reporter rather than the censo-sync epicenter. Targeted inspection supplied the decisive evidence. `_censo_sync.py` contains no adapter import, `importlib`, `__import__`, or string-based adapter target. The facade's PEP 562 branch lazily loads `_censo_sync` itself, not an adapter. The service function-locally imports the application-owned `_repository`; that module owns its concrete storage boundary and has its own explicit ledger pin, so it is not a substitute direct edge from `_censo_sync`.

The adapter names associated with `_censo_sync` in `test_lazy_import_policy.py` are historical allowlist-superset declarations. The gate discovers live AST import sites and permits the live set to shrink below the declared ceiling; those data rows neither import nor dispatch adapters and therefore do not revive the removed waiver.

No compatibility path, production waiver, test double, skip, or destructive worktree operation was introduced. S04 is the only current contract repair gate.
