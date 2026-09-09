---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:295d38d3c3fc0314b790c599e3469e2caa3b25ae46f325dfe4f9fc3e34aece74'
step_id: 'S280'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only review-package signing strict-load facade, missing-before-mint error registration, and load-only parser; migrate persistence and concurrency assertions to the live ensure owner while retaining the live public-key projection, run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `review-package signing module`
- `focused signing tests`
- `error registry`

## Changes

- `M` `src/cadrumo/application/modelo/review_package_signing.py`
- `M` `src/cadrumo/application/modelo/tests/test_review_package_signing.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for strict-load/error symbols -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` focused signing/keypair tests -> `8 passed, 9 deselected`
- `verify:` exact reachability -> `260 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The strict signing-key load had only tests as callers; the live ensure owner already loads, validates, or mints the encrypted keypair. Missing-before-mint was therefore not product behavior. Persistence, normalization, foreign-bucket refusal, concurrent mint convergence, signing, and verification remain covered through ensure. The public-key projection stays because live CLI commands consume it. Exact unused symbols improved from 261 to 260.
