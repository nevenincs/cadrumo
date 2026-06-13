---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S05'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---

# `schema-hardening` `P03.S05`

Authored the next evidence-grounded M100 continuity slice using generic
continuity records.

- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/casillas/0988-1038.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0985-1038.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/continuidad/1038-2023-2024-unchanged.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/continuidad/1038-2024-2025-retired.toml`
- Created: `.vault/exec/2026-05-28-schema-hardening-continuity-conformance/2026-05-28-schema-hardening-continuity-conformance-P03-S05.md`
- Created: `.vault/audit/2026-05-28-schema-hardening-continuity-conformance-p03-s05-review.md`

## Description

Selected M100 casilla `1038` from the prior continuity inventory because it is
an exact stable-signature candidate across 2023 and 2024 and is absent as a
casilla in 2025. Added continuity id
`irpf.deduccion-autonomica.galicia.otras` to the 2023 and 2024 casilla
records, declared an `unchanged` evolution for 2023 to 2024, and declared a
`retired` evolution for 2024 to 2025.

No schema, loader, or modelo-specific validator behavior was added in this
step.

## Tests

- Direct registry load confirmed 2023 and 2024 casilla `1038` carry the same
  continuity id, 2024 declares `m100-1038-2023-2024-unchanged`, 2025 declares
  `m100-1038-2024-2025-retired`, and 2025 has no casilla `1038`.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

All pytest checks passed after the S10 file-size gate repair. Committed-registry
and cross-revision tests emitted the existing M347 semantic-role singleton
warnings.

## Notes

This slice intentionally avoids broad M100 strict rollout. It adds one audited
continuity surface and leaves unrelated repeated-id drift advisory.
