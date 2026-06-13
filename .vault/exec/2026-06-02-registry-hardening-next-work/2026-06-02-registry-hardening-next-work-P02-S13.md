---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'P02.S13'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-schema-hardening-m100-label-legal-continuity-candidate-research]]'
---

# P02.S13 Execution Record

## Step

`P02.S13`: Author one M100 label-and-legal-reference continuity slice;
`src/aeat/_data/registry/aeat/modelos/100`.

## Result

Completed. M100 casilla `0070`, `Vivienda habitual en {year}`, now carries
`continuidad_id = "irpf.inmueble.vivienda-habitual-flag"` in revisions `2020`
through `2025`.

Continuity evolution fragments were added under the existing generic
`casilla_continuidad_evolutions` contract. The slice declares direct-pair
evolution records for the complete six-revision surface:

- `label_and_legal_refs_evolved` where both the annual label and legal
  references differ.
- `label_evolved` where only the annual label differs.

No schema, loader, or validator semantics were changed.

## Artifacts

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/casillas/0065-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/casillas/0069-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/casillas/0070-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/casillas/0071-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0071-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0225-0070.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/continuidad/0070-2020-2021-label-and-legal-refs-evolved.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/continuidad/0070-2021-2022-label-evolved.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/continuidad/0070-2022-2023-label-evolved.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/continuidad/0070-2023-2024-label-evolved.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/continuidad/0070-2024-2025-label-and-legal-refs-evolved.toml`
- `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `2026-06-02-registry-hardening-next-work-p02-s13-review`

## Verification

- Direct M100 load confirmed `0070` has the expected continuity id in revisions
  `2020` through `2025` and the expected direct-pair evolution kinds.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0063_legal_refs_is_loaded src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0070_label_and_legal_refs_is_loaded -q`
  - Result: 2 passed in 74.80s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_cross_revision_validator_accepts_committed_corpus src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate -q`
  - Result: 2 passed in 136.62s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_tree_loads_directory_modelos src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_directory_source_inventory_lists_every_revision_fragment_toml -q`
  - Result: 2 passed in 255.21s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 1 passed in 6.18s.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
  - Result: all checks passed.
