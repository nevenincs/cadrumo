---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:1602ca640ccd0ff143b47a7f45efbc9b7cce5aa12e3b0fa6277df3a9dadc26e8'
step_id: 'S383'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Run the full src/aeat test suite and confirm green, sequentially re-running any registry-suite failure before triaging it as a regression

## Scope

- `src/aeat`

## Description

Ran the full `src/aeat` suite and triaged every failure by owner before taking the Step's completion as owner-scoped green.

- Ran `uv run --no-sync pytest src/aeat -n auto -q --tb=short` with the full output captured to disk (no truncation before the tee), per the background-capture discipline.
- Result: 53 failed, 12158 passed in 563.85s. Extracted the full sorted FAILED list from the on-disk log.
- Re-ran the import-hygiene gate and the registry-suite failures SEQUENTIALLY (`-n0`) before triaging, per the loader-cache-race discipline.
- Confirmed the campaign's own gate (`test_import_hygiene_gate.py`) is green sequentially for the production Family-1 and Family-4 assertions; the two extra gate failures seen only under `-n auto` (`test_family3_genuine_duplicate_symbols_...`, `test_production_family1_violations_are_exactly_the_named_baseline_set`) were parallel/peer-churn races that pass on `-n0`.
- Triaged all 53 failures to owner: two are the SEPARATE test-only-debt family (five new peer test reaches); the remaining ~49 are tree-wide structural/inventory and registry-authoring gates owned by other concurrent campaigns, verified in peer files, none an import-centralization surface.

## Outcome

Owner surface is green: collect-only clean, the import-hygiene gate's production Family-1 and Family-4 assertions pass sequentially, and every campaign rewrite is behavior-preserving (object-identity verified). All 53 full-suite failures are triaged as peer-owned tree-wide/registry/inventory gate reds and are formally deferred to their owning campaigns per `full-tree-gate-must-distinguish-owner` and the do-not-absorb directive. The full failure inventory and per-owner triage are recorded in the campaign audit under `closeout-new-2-full-suite-peer-reds`. Step taken as owner-scoped green with the peer reds fully disclosed, not absorbed.

## Notes

The literal whole-tree "suite green" is not achievable in this shared worktree at HEAD because 53 unrelated peer campaigns' gates are red; the same disposition was reached by the campaign's own 2026-07-02 audit (then 31 failures). This closeout made zero source-code changes, so it introduced none of these failures. Registry failures (M100-2025 profile-binding count 38 vs pinned 37, M202/M210/M349 BOE-corpus grounding) reproduce sequentially — real, but peer-owned registry-authoring debt, not loader-cache races.
