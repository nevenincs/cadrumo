---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-01'
modified: '2026-06-01'
step_id: 'S06'
related:
  - "[[2026-05-28-schema-hardening-continuity-conformance-plan]]"
---

# Record verification evidence residual risks and next-step decision points

## Scope

- `.vault/exec`

## Description

Ran the four verification commands declared in the plan's Verification
section against the current chore/eliminate-shims tip.

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`

## Outcome

ruff: 107 errors reported, 97 auto-fixable. The errors are package-wide
(unsorted-imports / I001 dominates). They are pre-existing
shared-worktree state introduced by the broader ruff sweep landing on
this branch (commit `3ba193a13` lint: ruff --fix safe-autofix sweep
across src/) and continuing peer-agent activity in the registry
subpackage. They are not authored by this plan's Steps and do not
gate P02/P03 completion.

pytest (combined run across the three test modules): 92 passed, 1
failed, 8 warnings.

- Failing test: `test_committed_registry_toml_files_stay_reviewable`
  in `src/aeat/domain/calculations/registry/test_loader_directory_mode.py`.
  This is the registry TOML file-size and fragmentation regression
  gate from P03.S04. The gate is currently triggered by
  shared-worktree corpus growth (peer-agent registry-authoring work
  in flight on this branch); it is not authored by P02 changes.
  Classified as a pre-existing failure attributable to peer-agent
  corpus growth, not to this plan's validator-conformance work.

- Warning surfaced: `semantic_role 'contraparte_importe_q4'` appears
  on exactly one casilla; advisory-only warning emitted by
  `_validate_semantic_roles.py` line 147. Not a regression — the
  warning surface is by design.

## Notes

Residual risks to close before this plan reaches 100 percent:

- P02.S02 (validator semantics for retired/unmatched continuity) and
  P02.S03 (matching real-behavior tests) still open. Per the plan's
  Parallelization, these depend on P05 governing-comment placement
  which is already complete. No technical blocker remains; pending
  authoring time only.
- P03.S05 (next M100 continuity slice using only generic continuity
  records) gated on P02 completion per the plan's stated order.

Next-step decision points:

- Decide whether the P03.S04 file-size gate's failure on peer corpus
  growth justifies relaxing the threshold or whether the corpus
  growth itself requires fragmentation work in its originating plan.
  Recommend coordinating with the registry-corpus-authoring track
  rather than treating it as a P03 regression.
- The P02 validator work should be paired with the M100 slice
  authoring (P03.S05) in a single commit to keep evidence and
  validator semantics co-located.
