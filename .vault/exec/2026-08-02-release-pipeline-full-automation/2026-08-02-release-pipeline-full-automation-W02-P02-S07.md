---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:b62c89100d30b1ca1c0cf154bc24ec780ec1c71fd8a59894d7e6e792e568fef9'
step_id: 'S07'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Derive the acquisition lanes a release must dispatch from the same claimed-channel authority publication_inputs and the readiness gate already read, so an unclaimed channel is never dispatched and a claimed one can never be skipped, and so flipping a channel availability to available arms its lane with no workflow edit, gate: uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs passes with cases covering the current descriptor claiming python only, a descriptor claiming scoop and homebrew, and a claimed channel absent from the source mapping refusing rather than passing unproven

## Scope

- `dev/packaging/publication_inputs.py`
- `dev/packaging/tests/test_publication_inputs.py`

## Description

Added `acquisition_lanes(descriptor)` to `dev/packaging/publication_inputs.py`, derived from the SAME `SOURCE_INPUT_BY_CHANNEL` mapping the publish-dispatch demand (`demanded_inputs`) already reads — no second hand-maintained set. A claimed channel whose evidence source IS the cohort input itself (`python`, whose evidence rides the packaging-smoke run that produced the cohort) needs no acquisition dispatch; every other claimed channel is a lane. A claimed channel entirely absent from `SOURCE_INPUT_BY_CHANNEL` is excluded from the lane set (never silently treated as lane-free) and stays caught by the pre-existing `unmapped_claimed_channels`/`refusals` fail-closed path.

## Outcome

Gate green: `uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs` — 17 passed (10 pre-existing + 7 new). Coverage: today's descriptor (python only claimed) yields zero lanes; claiming scoop/homebrew individually and together arms the corresponding lane(s) with a negative control per channel; reverting availability disarms the lane with no code change; an unmapped claimed channel is excluded from `acquisition_lanes` and still refused by the existing fail-closed path; `python` is never a lane even when every channel in the descriptor is claimed.

## Notes

No incidents.
