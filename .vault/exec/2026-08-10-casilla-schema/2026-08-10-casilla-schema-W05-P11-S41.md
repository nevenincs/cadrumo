---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:6eb077a48f510ad937550c9aa4ec4d81d5e5368860ca96d9a33d1a5c4675fbd0'
step_id: 'S41'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# correct the standing collect gate to measure every tracked test root

## Scope

- `.vault/plan/2026-08-10-casilla-schema-plan.md`

## Description

- Ground the collect-only behavior in the project pytest configuration and the prior full-collection audit.
- Replace the ambiguous bare collect command with a serial collection that clears inherited `addopts` and names every tracked test root.
- Execute each candidate boundary and retain only the one that measures the intended tracked suite.

## Outcome

The plan's global gate now names `uv run --no-sync pytest src dev packaging --collect-only -q -n 0 --override-ini=addopts=`. The empty `addopts` override prevents the project default from selecting only the unit lane; the three positional roots cover every test file tracked by Git while excluding transient untracked probe trees in the shared worktree.

## Verification

- Mandatory code RAG passed and ranked the real marker-selection reachability evidence.
- Mandatory Vault RAG passed and ranked the S01 audit's established full-collection command plus this plan.
- The first candidate without positional roots exited zero with `29087 tests collected`, proving all marker cohorts only within configured `testpaths`; formal review correctly rejected its full-repository claim because it omitted 270 tracked `dev` test files.
- The second candidate with positional root `.` reached the omitted population but also admitted untracked shared-worktree probe copies, producing `32280 tests collected, 2090 errors`; it was rejected as a non-reproducible tracked-suite boundary.
- `git ls-files '*test_*.py'` identified the complete tracked root set: 2849 files under `src`, 271 under `dev`, and 4 under `packaging`, with no fourth tracked root.
- The final exact command over `src dev packaging` exited zero with `32280 tests collected in 71.62s`.
- Every plan body update used `vaultspec-core vault set-body`; no hand edit or unrelated plan-state mutation occurred.

## Notes

The initial combined plan-update and exec-scaffold command timed out after 34 seconds while VaultSpec completed both writes. Read-only inspection confirmed success before any retry. The failed `.` collection is retained as boundary evidence, not described as a product-test failure.
