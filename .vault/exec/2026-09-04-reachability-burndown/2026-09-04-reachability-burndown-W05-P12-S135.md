---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:c2f2ff07c1230ac2849c82faaa1f76921f9938a9829c57500f00270424850c28'
step_id: 'S135'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Refine the Modelo-specific regulatory embed detector by AST context so arithmetic identities, schema bounds, docstrings, regular expressions, and other non-policy literals are excluded structurally while planted regulatory rates, filing years, and operator prose still red the zero-target gate

## Scope

- `modelo embed scan`
- `detector-teeth tests`
- `live quality signal`
- `and cadence guidance`

## Changes

- `M` `dev/registry/analysis/modelo_embed_scan.py`
- `M` `dev/registry/tests/test_modelo_specific_embed_scan.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/modelo_embed_scan.py dev/registry/tests/test_modelo_specific_embed_scan.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/registry/tests/test_modelo_specific_embed_scan.py` -> `pass`

## Notes

The live zero-target gate moved from 97 candidate findings to 26 semantically scoped findings and remains red. The 26 are nine module-level years, sixteen operator-facing applicability messages, and one non-identity decimal percentage.
