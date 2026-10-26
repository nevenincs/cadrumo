---
tags:
  - '#audit'
  - '#edition-delta-authoring'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:21ced960ed2c607f0106df97f1863442a65008b33987d9eb2dbb386785b89866'
related: []
---
# `edition-delta-authoring` audit: `scoped migration loading`

## Scope

Reviewed the modelo-scoped loading path used by `dev/registry/edition_delta_migration.py` and `dev/registry/edition_round_trip.py`, together with the owning migration tests. The review assessed whether unrelated registry failures cease blocking migration without weakening the publication boundary.

## Findings

### fixture-source-state | high | The proposed fixture loader made the suite consume mutable migrated source

The initial test-helper change used the direct disk loader against a bundled Modelo 303 that is already delta-authored, invalidating the full-copy migration fixture. Resolution: the test-helper change was removed; fixture semantics remain unchanged. The existing broader suite is still blocked by unrelated live governed-fact validation failures, which are outside this scoped change.

### target-validation-boundary | medium | Modelo-only planning initially allowed no-export publication without full validation

Modelo-local typed loading is appropriate for planning and structural round-trip comparison, but it does not perform complete authority validation. Resolution: immediately before `--apply` displaces any production path, the staged registry is compiled as a complete validated authority. Dry runs retain scoped loading; publication retains the full authority boundary.

## Recommendations

- Keep planning and content comparison modelo-local so unrelated registry defects cannot suppress migration diagnostics.
- Keep the complete staged-authority validation immediately before publication and retain focused coverage for both boundaries.
