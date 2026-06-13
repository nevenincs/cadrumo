---
step_id: S220
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P09.S220 — semantic-intent drift sampler assertion test

## Outcome

Created `src/aeat/test_semantic_intent_sampler.py` with three tests:
- `test_sampler_produces_stable_deterministic_sample`: two calls with seed=47 produce
  identical 20-file lists; corpus >= 20 files.
- `test_sampler_output_covers_multiple_packages`: sample spans >=2 top-level subpackages.
- `test_sampler_records_drift_candidates_without_failing`: heuristic runs without error;
  drift candidates are returned as a list (may be empty or non-empty; both acceptable).

Seed is fixed at 47. Sample is drawn from `sorted(_SRC_ROOT.rglob("test_*.py"))` to
guarantee ordering stability across runs.

## Files touched

- `src/aeat/test_semantic_intent_sampler.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/test_semantic_intent_sampler.py -q` — 3 passed.
