---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b97426714ceb7b3264a49c7146ff0831aef1b473d3cd65b510c42b6bb2fd5f65'
step_id: 'S36'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Revalidate ModeloDraft as a required canonical RegistrySnapshotRef carrier with no duplicate coordinate path

## Scope

- `src/cadrumo/domain/filing/schema.py`
- `src/cadrumo/adapters/persistence/profile/filing_drafts.py`

## Changes

- `verify:` `uv run pytest -q -n 0 dev/quality/tests/test_registry_revision_stamp_coverage.py` -> `pass`
