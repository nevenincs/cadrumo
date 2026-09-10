---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:defc956a8f0032bec84b88d738bed602117b038b5433e401c08716631e856810'
step_id: 'S07'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [L | opus-medium] Adjudicate the modelo that renumbers boxes under stable identifiers, producing evolution records where the chain is real and an explicit refusal where it is not. This may not be mechanisable. Proof: every renumbered box is chained with evidence or refused by name.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/309`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2004-2015/casillas/cdecl.ejercicio__cwire.observaciones.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2004-2015/casillas/cdecl.rg-base-01__cdecl.resultado-24.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2016-2017/casillas/cdecl.periodo__cdecl.resultado-24.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2018-2022/casillas/cdecl.periodo__cdecl.resultado-24.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2023-y-siguientes/casillas/cdecl.periodo__cdecl.resultado-24.toml`
- `A` `dev/registry/analysis/casilla_lineage_rulings.toml` (two 309 blocks appended; the file is created by S06 and lands in S06's commit)
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_origin.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

## Notes

- Counts: 47 chains; 70 `grounded` rows (41 at 2004-2015>2016-2017, 29 at 2018-2022>2023-y-siguientes); 61 `seeded` middle rows; 47 chain-start rows carrying `continuidad_id` with no origin; 0 chains blocked by the semantic-linkage gate.
- Withheld: `decl.transmitente-apellidos` 2004-2015>2016-2017, a split of 2004 campo 9 into 2016 campi 13 and 14.
- Skipped work: `decl.transmitente-pais` 2004-2015>2016-2017 is held, not chained. It diverges on `data_type` and `semantic_role`; `CasillaEvolutionKind` has no representation-change member, and `repurposed` asserts a different meaning. No evolution record was written.
- Measured on HEAD `9dc3acaed7f2c4ca53c1143ab449641e1a0e1f03`.
- Follow-on for a later step: chaining `decl.transmitente-pais` needs a representation-change member in `CasillaEvolutionKind`, a schema decision outside this step.
