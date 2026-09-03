---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:e8c8cad730a600c57c9d335169e53dfbdc4f193ab0e199a8c6ebbd779d0bfcc4'
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
- Added outside-hardlink refusal and post-precheck hardlink-race coverage; the canonical sentinel remains byte-identical.
