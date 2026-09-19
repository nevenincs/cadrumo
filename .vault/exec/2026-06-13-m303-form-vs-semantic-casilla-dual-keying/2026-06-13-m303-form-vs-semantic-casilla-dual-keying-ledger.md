---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:46c99f252d1a628236968cc7d88acf7561da0da66f103027ad3998c0db954bcf'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---

# `m303-form-vs-semantic-casilla-dual-keying` ledger

## Changes

- `S01` `T` `.vault/reference/2026-06-13-m303-form-vs-semantic-casilla-dual-keying-reference.md`
- `S02` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
- `S03` `T` `verify the calculated box 09 equals iva.repercutido.general on a ledger calculate`
- `S03` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
- `S04` `T` `verify box 06 equals iva.repercutido.reducido on calculate and via pull (one-aggregation-path parity)`
- `S04` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
- `S05` `T` `verify box 03 equals iva.repercutido.super-reducido registry-authoritatively`
- `S05` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
- `S06` `T` `verify box 11 equals that source`
- `S06` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
- `S07` `T` `verify box 13 equals that source`
- `S07` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
- `S08` `T` `ensure topological order computes iva.cuota-devengada-total before box 27`
- `S08` `T` `and verify box 27 equals the total registry-authoritatively`
- `S08` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`
- `S09` `T` `verify box 29 equals iva.soportado.interiores on calculate and pull (parity)`
- `S09` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`
- `S10` `T` `verify box 33 equals that source`
- `S10` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`
- `S11` `T` `if P01 deferred box 37 as ambiguous`
- `S11` `T` `leave it manual and keep the Stage 1 advisory for it instead`
- `S11` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`
- `S12` `T` `ensure topological order computes iva.cuota-deducible-total before box 45`
- `S12` `T` `and verify box 45 equals the total registry-authoritatively`
- `S12` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`
- `S13` `T` `register each id in the revision formula list`
- `S13` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`
- `S14` `T` `src/aeat/domain/calculations/registry/_schema.py`
- `S15` `T` `src/aeat/domain/calculations/registry/_validate_surfaces.py`
- `S16` `T` `src/aeat/application/modelo/_verification_actions.py`
- `S17` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`
- `S18` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`
- `S19` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`
- `S20` `T` `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`
- `S21` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/`
