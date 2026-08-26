---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
step_id: 'S05'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Reconcile the annual-Orden runtime parse-cache row onto the build-generated census artifact and prove parse bypass plus identity-drift fallback

## Scope

- `src/cadrumo/domain/calculations/registry/m303_orden_census_artefact.py`
- `src/cadrumo/domain/calculations/registry/m303_orden_manifest.py`
- `src/cadrumo/domain/calculations/registry/tests/test_m303_orden_census_artefact.py`

## Description

The original S05 runtime-cache mechanism had been superseded by commit `e49dfc16ab`, which moved annual-Orden compilation onto a shipped, versioned census artifact. A second runtime cache would duplicate authority and was not added. The existing artifact is included in the supplementary-Orden fingerprint set, rejects stale extractor/source identities, and falls back to source extraction when it cannot be trusted.

## Outcome

Commit `4232dd1eb7` adds the missing extractor-event proof without changing production code. Two unchanged authority compilations against a valid census artifact call `extract_m303_annual_orden_source` zero times. Tampering the artifact source digest makes the compiler reject the fast path, extract exactly the selected annual sources, and produce authority equal to the valid artifact path.

The focused integration selector passed 1 test in 8.08 seconds; the complete census-artifact module passed 15 tests in 13.69 seconds. Ruff format/check and `git diff --check` were green. No Modelo 200 path was touched.

## Notes

This is a reconciliation of the stale planned mechanism, not a claim that the obsolete runtime-cache design was implemented. The build-generated census artifact is the single surviving compile-once authority.
