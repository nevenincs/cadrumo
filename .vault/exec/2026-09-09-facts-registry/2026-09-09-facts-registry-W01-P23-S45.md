---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:976f4abd44e83a89391da00d492e5bb4b7af667b2a4c834b6db756fabc173b3b'
step_id: 'S45'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Run shipped-entrypoint reachability at the Wave 1 handoff

## Scope

- `justfile audit-unreachable-code and dev/audit/unreachable_code.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P23-S45.md`
- `verify:` `just audit-unreachable-code` -> `fail`

## Notes

The first boundary run found two Wave 1 findings: unreachable `facts.resolution` and unused `fact_provider_for_directory`. Commit `f4894ac261` integrated authority resolution and removed the unused helper. The rerun contains no facts-registry finding; it still reports 31 unreachable modules and 787 unused symbols outside this campaign.
