---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:6a988e94f043d4877915762c976513f635161cf855da773fba41af7a99db52c7'
step_id: 'S43'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Add a carrier-coverage ratchet enumerating every durable registry-derived schema and its canonical stamp strategy

## Scope

- `dev/quality`
- `src/cadrumo/tests`

## Changes

- `A` `dev/quality/tests/test_registry_revision_stamp_coverage.py`
- `verify:` `uv run pytest -q -n0 dev/quality/tests/test_registry_revision_stamp_coverage.py` -> `pass` (39 tests)
