---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:08481e0af6cd19773e453633f0c97b5976ef7ab7d985f39ae9bc8aa6b49bc5a2'
step_id: 'S330'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the Modelo 232 literal-set duplicate detector and raw type-hint assertions

## Scope

- `Modelo 232 singularity gate`
- `direct hydration and registry behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_modelo_232_codigo_singularity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/modelos/tests/test_m232_row_capacity.py src/cadrumo/domain/calculations/registry/tests/test_modelo_232_registry.py src/cadrumo/application/calculations/tests/test_modelo_232_operaciones_vinculadas_fidelity.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
