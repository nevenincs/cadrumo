---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'P02.S11'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-schema-hardening-m100-legal-ref-continuity-candidate-research]]'
---

# P02.S11 Execution Record

## Step

`P02.S11`: Author one M100 legal-reference-only continuity slice;
`src/aeat/_data/registry/aeat/modelos/100`.

## Result

Completed. M100 casilla `0063`, `Propiedad (%)`, now carries
`continuidad_id = "irpf.inmueble.porcentaje-propiedad"` in revisions `2020`
through `2025`.

Continuity evolution fragments were added under the existing generic
`casilla_continuidad_evolutions` contract. During validation, the strict
cross-revision gate proved that adjacent-year evolution declarations are not
enough for a legal-reference-only surface when non-adjacent strict revision
pairs also diverge. The committed slice therefore declares direct
`legal_refs_evolved` records for every divergent revision pair and `unchanged`
records for the adjacent same-reference transitions.

No schema, loader, or validator semantics were changed.

## Artifacts

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/casillas/0058-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/casillas/0062-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/casillas/0063-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/casillas/0064-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0064-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0218-0063.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/continuidad/0063-2020-2021-legal-refs-evolved.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/continuidad/0063-2021-2022-unchanged.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/continuidad/0063-2022-2023-unchanged.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/continuidad/0063-2023-2024-unchanged.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/continuidad/0063-2024-2025-legal-refs-evolved.toml`
- `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `2026-06-02-registry-hardening-next-work-p02-s11-review`

## Verification

- Direct M100 load confirmed `0063` has the expected continuity id in revisions
  `2020` through `2025` and the expected direct-pair evolution kinds.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0582_is_loaded src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0063_legal_refs_is_loaded -q`
  - Result: 2 passed in 45.14s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_cross_revision_validator_accepts_committed_corpus src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate -q`
  - Result: 2 passed in 102.62s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_tree_loads_directory_modelos src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_directory_source_inventory_lists_every_revision_fragment_toml -q`
  - Result: 2 passed in 114.09s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 1 passed in 5.10s.
