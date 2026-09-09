---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ebf632f8300e0bf89d4aca0a32d1a870e68b936e13562391f909407fa6dc4b32'
step_id: 'S350'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unwired wizard registered-values and legal-zone projections and their module-status inventory tests.

## Scope

- `wizard projections and tests`
- `flow owner behavior`
- `locale rationale`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/application/wizard/_registered_values.py`
- `D` `src/cadrumo/application/wizard/legal_zone.py`
- `D` `src/cadrumo/application/wizard/tests/test_registered_values.py`
- `D` `src/cadrumo/application/wizard/tests/test_legal_zone.py`
- `D` `src/cadrumo/application/wizard/tests/test_public_definition_identity.py`
- `M` `dev/locales/tests/test_tr_constant_naming_convention.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/flows/tests/test_definition.py src/cadrumo/application/flows/tests/test_copy_assembly.py src/cadrumo/application/flows/tests/test_line_frontend.py src/cadrumo/application/wizard/tests/test_commands_helpers.py src/cadrumo/application/wizard/tests/test_flow_description_keys.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/locales/tests/test_tr_constant_naming_convention.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
