---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:b76bd30da3620910852eb0e18c48cbaa5dfada49fe3e81df2258f2ede2ded7c2'
step_id: 'S280'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
