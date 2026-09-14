---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:606063a0c68a9742664745b63b0610b8911efaaf5786f8f5ef10062b4bb1c104'
step_id: 'S16'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# Regenerate and measure the tracked v4 artifact, proving semantic equality and the compactness budget

## Scope

- `src/cadrumo/_data/registry/authority/authority.json`
- `dev/registry/pipeline/`

## Changes

- `M` `dev/registry/tests/test_authority_artifact_round_trip.py`
- `M` `src/cadrumo/_data/registry/authority/authority.json`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline publish-authority` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/registry/tests/test_authority_artifact_round_trip.py::test_the_full_bundled_registry_round_trips_through_a_publication` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/registry/tests/test_authority_artifact_round_trip.py` -> `pass`
- `verify:` `uv run --no-sync python -m py_compile dev/registry/tests/test_authority_artifact_round_trip.py` -> `pass`
- `verify:` `git diff --check -- dev/registry/tests/test_authority_artifact_round_trip.py src/cadrumo/_data/registry/authority/authority.json` -> `pass`

## Notes

The remaining atom-focused tests in the same module currently encounter unrelated concurrent Modelo 100 continuity-grounding refusals while constructing their shared compiler fixture. The S16 full canonical publication, tracked typed-equality, integrity, currentness, and 64 MiB budget gate passed independently.
