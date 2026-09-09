---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:87ac3a07c7ba8220da4fc66b82f54bfff2c4a5cb2ee2110c92355dcc0af3b68d'
step_id: 'S349'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only CLI manager frontend helper and its source-policy and retired-symbol inventory test.

## Scope

- `manager frontend remnant`
- `wizard behavior tests`
- `live profile CLI`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/entrypoints/cli/config/_manager_frontend.py`
- `D` `src/cadrumo/entrypoints/cli/config/tests/test_manager_frontend_routing.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/wizard/tests/test_commands_helpers.py src/cadrumo/application/wizard/tests/test_flow_description_keys.py src/cadrumo/application/wizard/tests/test_wizard_validation_localization.py` -> `pass`
- `verify:` `uv run --no-sync aeat config profile --help` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
