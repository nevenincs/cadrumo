---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:dec8fa423e9551f12cb0e8dea31e4ed16c75f5ce0592955d25c6150bc25c0ff8'
step_id: 'S42'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Add anti-compatibility tests that remove each required coordinate from encrypted payloads and prove strict load refusal

## Scope

- `src/cadrumo/adapters/persistence/profile/tests`
- `src/cadrumo/application/calculations/tests`

## Changes

- `M` `src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_filing_export_replay_custody.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_observation_store_roundtrip.py`
- `M` `src/cadrumo/application/calculations/tests/test_revision_stamp_roundtrip.py`
