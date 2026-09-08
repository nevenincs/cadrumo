---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:24c1e7b9f91332297a07832f4a9e3dd2f3ce22c140b0ec9d3aa476faf9f97160'
step_id: 'S254'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unwired art 105 Cinco interrupted-seed projector and synthetic suite

## Scope

- `Retain the register history model and live annual prorrata resolver`
- `remove the application seed DTO and builder no workflow calls`
- `correct sector-lifecycle prose`
- `amend the contradicted ADR implementation prescription`
- `run focused prorrata gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `M` `src/cadrumo/application/calculations/prorrata_regularizacion.py`
- `D` `src/cadrumo/application/calculations/tests/test_prorrata_interrumpida_seed.py`
- `M` `src/cadrumo/application/prorrata_register/sector_lifecycle.py`
- `M` `.vault/adr/2026-07-07-prorrata-art105-cinco-interrupted-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/calculations/prorrata_regularizacion.py src/cadrumo/application/prorrata_register/sector_lifecycle.py` -> `pass`
- `verify:` `uv run --no-sync python -c "from cadrumo.application.calculations import prorrata_regularizacion; from cadrumo.application.prorrata_register import sector_lifecycle"` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/calculations/tests/test_prorrata_regularizacion.py src/cadrumo/application/prorrata_register/tests` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The broad prorrata run had 31 passes and unrelated existing failures: parallel workers shared locked KDF scratch paths, and peer changes now require registry snapshot references and official declaration-type headers in older fixtures. No failure imports or exercises the deleted projector; the modified modules pass lint and import, and exact reachability removed the reported symbol.
