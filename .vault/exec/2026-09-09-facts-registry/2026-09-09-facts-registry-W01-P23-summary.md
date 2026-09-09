---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:bc6ab397fc4823a667086d6a043a71d6511906929ca9cc61f1a6fb4bed468652'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` `W01.P23` summary

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `verify:` `just check-types` -> `fail`
- `verify:` `just audit-dead-code` -> `pass`
- `verify:` `just audit-unreachable-code` -> `fail`

## Notes

The failed commands contain no remaining Wave 1 facts-registry finding. Type checking reports 50 existing `ty` diagnostics outside the campaign; reachability reports 31 unreachable modules and 787 unused symbols outside the campaign.
