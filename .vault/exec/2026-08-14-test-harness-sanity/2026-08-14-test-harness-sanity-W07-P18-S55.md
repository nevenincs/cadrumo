---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1dde64f78256803b16f87e43b4367e97b516e244c5b8d4ed61d5ea4552aefc3d'
step_id: 'S55'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize the exact secure-object-repository cluster without merging its divergent shape

## Scope

- `src/cadrumo/application/aggregation/tests`
- `src/cadrumo/application/modelo/tests`

## Description

- Replace the exact 17-member secure-object repository fixture cluster with one application-level canonical owner.
- Derive each existing module bucket identity from its real `_BUCKET_ID` and preserve function-scoped encrypted-runtime teardown.
- Keep every divergent local fixture closer to its consumers and refresh ownership evidence.

## Outcome

Seventeen identical `secure_objects` definitions now resolve to one function-scoped, non-autouse fixture in the application conftest. All target modules retain their existing bucket identity, while divergent fixture shapes continue to shadow the broader owner locally.

## Notes

Fixture setup and teardown succeeded for 16 representative targets; the seventeenth cannot collect because concurrent profile-custody work removed `profile_create_storage_span` from a downstream export support import. Representative behavior then encounters unrelated custody and IVA legal-grounding failures, so no broad green claim is made. Ruff, diff integrity, exact 17-definition census, missing-bucket negative control, visibility checks, and independent review passed. Sixteen target files also contain peer custody changes; only fixture-removal hunks were staged through index-level isolation.
