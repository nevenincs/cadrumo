---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:44aab0e21de26c43f845324b377adfc97acbaff416738934f88da4af4bcf1c42'
step_id: 'S04'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# Detect target-description, semantic-role, legal-reference, and source-SHA mutations at the historic-restoration boundary

## Scope

- `dev/registry/tests/test_m200_2024_restoration_candidates.py`

## Changes

- `M` `dev/registry/tests/test_m200_2024_restoration_candidates.py`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/registry/tests/test_m200_2024_restoration_candidates.py` -> `pass`

## Notes

- Added detectors for direct, traversal, and symlink-based containment in the canonical registry root, and asserted that the retired candidate aliases are absent from the module surface.
- Added real `SemanticMap`/official-design joining and coordinated map-plus-gap source-drift refusal coverage, including a parent-swap race proving canonical output is unchanged.
