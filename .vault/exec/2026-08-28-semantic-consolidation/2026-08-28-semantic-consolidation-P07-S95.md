---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c111270ad2f488866e98e6c4ec2058814ea2b579d61e8100387a2ab67922b455'
step_id: 'S95'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the deadlines, Google outbound and AEAT sede facades, repointing module-object imports and their body uses together

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/domain/deadlines/__init__.py`
- `M` `src/cadrumo/adapters/outbound/google/__init__.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/__init__.py`
- `verify:` `pytest src/cadrumo/domain/deadlines src/cadrumo/adapters/outbound/google src/cadrumo/adapters/outbound/aeat/sede -n 0 -m ""` -> `fail`

## Notes

1363 pass, 33 fail. Sixteen are live tests refusing without
CADRUMO_LIVE_TESTS_ENABLED / _GOOGLE, which is their design. The remainder --
six SedeParseError, one RegistryValidationError on a modelo-130 sign marker,
one KeyError on a modelo-111 export record, and four M210 deadline windows
resolving to None -- are all downstream of a peer's in-flight registry
refactor: 26 registry modules and 20 registry TOMLs are modified in the
working tree, and registry validation is all-or-nothing. This Step's diff to
`domain/deadlines` is imports and docstrings only.
