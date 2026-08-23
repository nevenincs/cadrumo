---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:9cfd32d1ee296f7584c9f1f1d7bbffeb58bc16d65b608cde1bda2498a9afe09f'
step_id: 'S23'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# verify every discovered capability and accepted destination candidate has exactly one census row

## Scope

- `dev/source_connectivity/tests/test_census_completeness.py`

## Description

- Give every structural discovery record a stable, location-independent capability identity.
- Freeze explicit candidate coverage and selector-backed remainder coverage in the canonical census.
- Refuse unknown, duplicated, unclaimed, or selector-drifted capabilities.
- Require advisory destination references to have exactly one census owner.
- Prove live-tree completeness and mutation-shaped digest failure with sequential tests.

## Outcome

The canonical census assigns all 428 independently discovered source capabilities exactly once. New
capabilities cannot be silently absorbed by broad remainder selectors because each selector is pinned
to the digest of its reviewed membership. Explicit rows retain inventory-first and amortization-second
campaign priority, while the reviewed remainder remains classified without duplicating calculation-route
authority.

## Notes

The initial targeted test command was rejected by the repository marker guard because the new test module
lacked a unit marker. The module was marked consistently with the adjacent discovery suite and the full
targeted run then passed: eight tests, sequential execution. Ruff passed on every touched Python surface.
