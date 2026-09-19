---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:08b406a31d0d1d3d7cd0c35955cc0a29ed5727e708b01294ba9ef896d22436e2'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `Review P05 S225 machine-secret channel tests`

## Scope

Independent review of immutable P05.S225 commit `e694afb6b6`, its exact five-path scope and execution record, the successful and refusal subprocess families, shared support topology, cleanup fixtures, live storage ownership imports, size/baseline/policy effects, and immutable plan isolation from peer P02 state.

## Findings

No triaged findings. `_machine_secret_channels_support.py` cohesively owns the real subprocess harnesses, transport helpers, registration/recovery material, snapshots, assertions, and keychain cleanup. The success/recovery/certificate family and the refusal family both import that support directly; the support does not import either test family, so no cross-test facade was introduced. Each test module retains a local autouse cleanup fixture, and a representative success/refusal run exercised both: 3 passed.

The harness imports the live storage builders directly from the defining `_profile_custody.py` and `_profile_login_session.py` modules, not the former storage facade. Rerun ruff and formatting passed. Independent collection reproduced 70 integration cases; the immutable execution record provides an executable command and literal JUnit result of `70 passed in 487.26s` with exit 0. The original test module is 654 lines, below the 1250 cap, and the feature diff has no baseline or policy change.

The immutable plan diff changes only the generated `body_hash` and P05.S225 checkbox. Its parent and commit blobs are distinct from the current peer worktree/default-index plan blob, which preserves unrelated P02 hunks; those peer changes are not attributable to S225.

## Recommendations

Approve P05.S225 as reviewed.
