---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:df5014704ea37bbe0c25f076b61cce9c359294e7247319010742597c103d8aaa'
step_id: 'S81'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Move full-corpus collectability out of unit while retaining bounded controls

## Scope

- `src/cadrumo/tests/test_every_test_module_is_collectable.py`

## Description

- Move the full-corpus collection proof into an integration-marked harness module.
- Keep source-discovery anti-vacuity and bounded malformed-module controls in the routine unit module.
- Update the canonical harness recipe and CI membership contract to select and preflight the full-corpus member explicitly.

## Outcome

Routine unit execution no longer recursively collects the repository. The dedicated harness owns the sole full-corpus proof, preflights it as one real test, and executes its child collection under a separately verdictable outer-serial lane.

## Notes

Ruff, formatting, bounded unit tests, explicit harness collection, recipe non-vacuity, CI behavioral controls, and diff integrity passed. The real full-corpus proof is currently red on existing shared-tree collection failures, including persisted temporary repository copies and unrelated project import gaps; this is an honest corpus-state verdict rather than a split failure, so no suppression or compatibility bridge was added.
