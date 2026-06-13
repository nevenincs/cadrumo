---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'P02.S14'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# P02.S14 Execution Record

## Step

`P02.S14`: Add committed-corpus regression coverage for M100 1038 continuity;
`src/aeat/domain/calculations/registry/test_cross_revision_drift.py`.

## Result

Completed. Added committed-corpus coverage for M100 casilla `1038`, the Galicia
`Otras deducciones` continuity surface.

The test now proves that:

- `1038` is loaded in M100 revisions `2023` and `2024`.
- Both loaded casillas carry
  `continuidad_id = "irpf.deduccion-autonomica.galicia.otras"`.
- M100 revision `2025` no longer carries casilla `1038`.
- The committed evolution chain contains `2023` to `2024` as `unchanged` and
  `2024` to `2025` as `retired`.

No registry TOML, schema, loader, or validator semantics were changed.

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_1038_retirement_is_loaded src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_cross_revision_validator_accepts_committed_corpus -q`
  - Result: 2 passed in 72.52s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate -q`
  - Result: 1 passed in 131.02s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0582_is_loaded src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0063_legal_refs_is_loaded src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0070_label_and_legal_refs_is_loaded -q`
  - Result: 3 passed in 115.27s.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
  - Result: all checks passed.
