---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b1b10f6caaa47ca9fccfbb949592eb42d6342e9e870c93fd6dd49b583eac9914'
step_id: 'S02'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | sonnet-high] Classify every assertion in the dev registry tests that requires findings to be non-empty or above a floor, as corpus-floor or detector-teeth, with file and line. Proof: a list whose counts reconcile with a fresh assertion sweep.

## Scope

- `dev/registry/tests`

## Changes

- `M` `.vault/plan/2026-09-09-registry-edition-authoring-plan.md`

## Notes

Classification only; no source file changed. The step's finding — that the flagged lines are anti-vacuity guards rather than removable assertions — was carried into the S03 Step row, which now says REPLACE and never delete.
