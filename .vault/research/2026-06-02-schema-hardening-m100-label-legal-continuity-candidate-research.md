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

# `schema-hardening` research: `m100 label-and-legal-reference continuity candidate`

Research goal: select one M100 continuity rollout candidate whose structural
identity is stable while both `label` and `legal_refs` drift across revisions.
The implementation step remains separate as `P02.S13`.

## Findings

### Candidate Derivation

The candidate scan loaded M100 with `load_modelo_directory`, walked repeated
casilla ids across revisions `2020` through `2025`, excluded any casilla already
carrying `continuidad_id`, and required stable structural identity fields:

- `section`
- `data_type`
- `semantic_role`

The scan then selected ids where both `label` and `legal_refs` differ across
the repeated revision set. That found 594 candidates.

### Selected Candidate

Selected candidate: M100 casilla `0070`.

Stable fields across all six revisions:

- `section`: `toma_datos_ampliada`, `inmuebles`, `inmueble`
- `data_type`: `boolean`
- `semantic_role`: `irpf_inmueble_vivienda_habitual_flag`

Revision labels:

- `2020`: `Vivienda habitual en 2020`
- `2021`: `Vivienda habitual en 2021`
- `2022`: `Vivienda habitual en 2022`
- `2023`: `Vivienda habitual en 2023`
- `2024`: `Vivienda habitual en 2024`
- `2025`: `Vivienda habitual en 2025`

Source files:

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/casillas/0065-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/casillas/0069-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/casillas/0070-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/casillas/0071-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0071-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0225-0070.toml`

Observed legal-reference signatures:

- `2020`: broad Ley 35/2006 article set from `art-17` through `art-32` with
  gaps matching the source metadata.
- `2021` through `2024`: stable narrower Ley 35/2006 set, `art-27`, `art-28`,
  `art-30`, `art-31`, and `art-32`.
- `2025`: broad Ley 35/2006 article set plus `ley-35-2006:art-99`,
  `rd-439-2007:art-109`, and `orden-hac-277-2026:art-3`.

No sampled revision currently declares a `continuidad_id` for `0070`.

## P02.S13 Recommendation

Author a narrow label-and-legal-reference continuity slice for M100 `0070`:

- Set `continuidad_id = "irpf.inmueble.vivienda-habitual-flag"` on the six
  casilla records for revisions `2020` through `2025`.
- Use the existing generic `casilla_continuidad_evolutions` schema.
- Declare direct-pair evolution records, not only adjacent-year records, because
  the strict validator compares all strict non-overlapping revision pairs.
- Use `label_and_legal_refs_evolved` for pairs whose label and legal references
  both differ.
- Use `label_evolved` for pairs where only the annual label differs.

Expected direct-pair evolution map:

- `2020` to `2021`: `label_and_legal_refs_evolved`
- `2020` to `2022`: `label_and_legal_refs_evolved`
- `2020` to `2023`: `label_and_legal_refs_evolved`
- `2020` to `2024`: `label_and_legal_refs_evolved`
- `2020` to `2025`: `label_and_legal_refs_evolved`
- `2021` to `2022`: `label_evolved`
- `2021` to `2023`: `label_evolved`
- `2021` to `2024`: `label_evolved`
- `2021` to `2025`: `label_and_legal_refs_evolved`
- `2022` to `2023`: `label_evolved`
- `2022` to `2024`: `label_evolved`
- `2022` to `2025`: `label_and_legal_refs_evolved`
- `2023` to `2024`: `label_evolved`
- `2023` to `2025`: `label_and_legal_refs_evolved`
- `2024` to `2025`: `label_and_legal_refs_evolved`

This direct-pair volume is a real metadata pressure signal. It should be
implemented mechanically for `P02.S13`, then considered in later architecture
work rather than solved by an ad hoc M100 exception.

## Verification

The candidate scan produced `candidates 594` after excluding already-authored
continuity ids and requiring stable `section`, `data_type`, and `semantic_role`
with both label and legal-reference drift.

Direct inspection of `0070` confirmed all six revisions have stable structural
identity and no existing `continuidad_id`.
