---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:92f514fd03cd75c70d268669154cac7bd5b7dd358471400ba8175e02024314c3'
step_id: 'S31'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Delete migrated statutory declarations but retain technical configuration

## Scope

- `src/cadrumo/core/external_constants.py`

## Changes

- `M` `.vault/audit/2026-09-11-facts-registry-s31-external-constants-retirement-audit.md`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `M` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `M` `dev/registry/tests/test_facts_external_constants_retirement.py`
- `M` `src/cadrumo/core/external_constants.py`
- `verify:` `uv run pytest -q -n 0 dev/registry/tests/test_statutory_authored_facts.py dev/registry/tests/test_facts_wave2_provider_handoff.py dev/registry/tests/test_wave2_fact_provider_handoff.py dev/registry/tests/test_facts_external_constants_retirement.py` -> `pass`
