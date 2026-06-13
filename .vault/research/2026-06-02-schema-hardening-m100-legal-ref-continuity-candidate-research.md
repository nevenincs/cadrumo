---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---

# `schema-hardening` research: `m100 legal-reference-only continuity candidate`

Research goal: select the next narrow M100 continuity rollout candidate after
the reviewability splits, without adding modelo-specific schema behavior or
turning repeated numeric casilla ids into automatic continuity.

## Findings

### Current Continuity State

The committed M100 registry already has continuity metadata for the first strict
stable slice and retirement slice:

- `0582` continuity exists across `2022` through `2025`.
- `1038` continuity exists for `2023` through `2024` and retirement exists for
  `2024` through `2025`.

Those candidates are therefore not the next legal-reference-only authoring
target. `1038` remains useful for the already planned committed-corpus
regression coverage in `P02.S14`.

### Candidate Derivation

The candidate scan loaded M100 with `load_modelo_directory`, walked repeated
casilla ids across revisions `2020` through `2025`, excluded any casilla already
carrying `continuidad_id`, and required the validator-owned identity fields to
stay stable:

- `label`
- `section`
- `data_type`
- `semantic_role`

The scan then selected ids whose `legal_refs` differed across revisions. That
found 1078 legal-reference-only candidates, including `0001`, `0062`, and
`0063`.

`0001` is a valid candidate but is a generic declaration selector. `0063` is a
clearer next slice because it is a concrete property-data casilla in the
inmueble surface.

### Selected Candidate

Selected candidate: M100 casilla `0063`.

Stable fields across all six revisions:

- `label`: `Propiedad (%)`
- `section`: `toma_datos_ampliada`, `inmuebles`, `inmueble`
- `data_type`: `ratio`
- `semantic_role`: `irpf_inmueble_porcentaje_propiedad`

Source files:

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/casillas/0058-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/casillas/0062-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/casillas/0063-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/casillas/0064-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0064-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0218-0063.toml`

Observed legal-reference signatures:

- `2020`: broad Ley 35/2006 article set from `art-17` through `art-32` with
  gaps matching the source metadata.
- `2021` through `2024`: stable narrower Ley 35/2006 set, `art-27`, `art-28`,
  `art-30`, `art-31`, and `art-32`.
- `2025`: broad Ley 35/2006 article set plus `ley-35-2006:art-99`,
  `rd-439-2007:art-109`, and `orden-hac-277-2026:art-3`.

No sampled revision currently declares a `continuidad_id` for `0063`.

## P02.S11 Recommendation

Author a narrow legal-reference-only continuity slice for M100 `0063`:

- Set `continuidad_id = "irpf.inmueble.porcentaje-propiedad"` on the six
  casilla records for revisions `2020` through `2025`.
- Add continuity evolution fragments using the existing generic M100
  `casilla_continuidad_evolutions` shape.
- Use `legal_refs_evolved` for `2020` to `2021`.
- Use `unchanged` for `2021` to `2022`, `2022` to `2023`, and `2023` to
  `2024`.
- Use `legal_refs_evolved` for `2024` to `2025`.

The slice should not change schema semantics, loader behavior, labels, sections,
data types, semantic roles, or existing legal-reference arrays.

## Verification

The candidate scan produced `candidates 1078` after excluding already-authored
continuity ids and requiring stable `label`, `section`, `data_type`, and
`semantic_role` with legal-reference drift.

Direct inspection of `0063` confirmed all six revisions have stable identity
fields and only `legal_refs` drift under the current validator-owned field set.
