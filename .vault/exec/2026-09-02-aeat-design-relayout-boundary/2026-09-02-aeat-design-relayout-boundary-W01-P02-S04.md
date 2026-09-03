---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:63272609fe1e21524bc39bbeb8f553ac28b980dee69bd430b21c0dbfb01710eb'
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

- The CLI parser rejects filesystem destination options, and captured stdout is deterministic proposal-only TOML without a `revisions` table.
- Runtime coverage forbids filesystem write calls and asserts that no destination-path writer surface or retired aliases is exported.
- Real `SemanticMap`/official-design joining and coordinated map-plus-gap source-drift refusal remain covered.
- Mutation detectors cover target description, semantic role, legal references, and source SHA; source identity is checked against the parsed pinned design.
