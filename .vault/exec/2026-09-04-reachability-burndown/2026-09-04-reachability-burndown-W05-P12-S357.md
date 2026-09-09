---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:49d0b25d3ab4a273d0037d0bc00d870af1b36cb8c99abbc28ac071bd8bd5ba92'
step_id: 'S357'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove unused operation-schema compatibility constants and a stale wizard locale-key export, replacing private-set inspection with validator behavior.

## Scope

- `operation registry and credential-free tripwire tests`
- `wizard format hints`
- `locale detector prose`
- `exact signal`

## Changes

- `M` `src/cadrumo/application/operations/registry.py`
- `M` `src/cadrumo/application/operations/tests/test_credential_free_field_tripwire.py`
- `M` `src/cadrumo/application/wizard/_format_hints.py`
- `M` `dev/locales/tests/test_tr_constant_naming_convention.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/operations/tests/test_credential_free_field_tripwire.py -q` -> `pass (18 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/operations/registry.py src/cadrumo/application/operations/tests/test_credential_free_field_tripwire.py src/cadrumo/application/wizard/_format_hints.py dev/locales/tests/test_tr_constant_naming_convention.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (264 unused symbols; down from 267)`
