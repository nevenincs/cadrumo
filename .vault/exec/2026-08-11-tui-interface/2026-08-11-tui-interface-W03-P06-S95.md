---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:263053ece43b96a7f6c954ab7bc2a60bc7f968bd1d679c3c4316c744c0225d2a'
step_id: 'S95'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Declare the acquisition-source capability, scope and authentication contract that W03.P06.S14 renders but no public surface currently supplies, so an operator sees which scopes and credentials a source requires and whether they are held, deriving each fact from the owning authority rather than a presentation-local policy, then render those facts on the source-action panel

## Scope

- `the public acquisition-source capability contract`
- `src/cadrumo/application/user_profile/acquisition_sources.py`
- `src/cadrumo/entrypoints/tui/profile/overview.py`
- `and focused capability and scope rendering tests`

## Changes

- `M` `src/cadrumo/application/user_profile/acquisition_sources.py`
- `A` `src/cadrumo/application/user_profile/tests/test_acquisition_sources.py`
- `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `A` `src/cadrumo/entrypoints/tui/profile/tests/test_acquisition_source_capability.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/profile/ src/cadrumo/application/user_profile/tests/test_acquisition_sources.py -q -m "unit or integration"` -> `pass` (29 passed)
