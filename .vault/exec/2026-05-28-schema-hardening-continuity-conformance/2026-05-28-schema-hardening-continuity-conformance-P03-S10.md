---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S10'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---

# `schema-hardening` `P03.S10`

Added generic completeness-manifest fragment merging and repaired discovered
file-size gate violations.

- Modified: `src/aeat/domain/calculations/registry/_loader.py`
- Modified: `src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness-manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness/casillas-0000-placeholder-0278.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness/casillas-0279-0568.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness/casillas-0569-1607.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness/casillas-1608-2236.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`
- Created: `.vault/exec/2026-05-28-schema-hardening-continuity-conformance/2026-05-28-schema-hardening-continuity-conformance-P03-S10.md`
- Created: `.vault/audit/2026-05-28-schema-hardening-continuity-conformance-p03-s10-review.md`

## Description

Added a generic revision-fragment merge rule for the singleton
`completeness_manifest` table. Scalar manifest fields still conflict if
multiple fragments disagree, while the manifest `casillas` array can now be
split across fragments and appended in deterministic loader order.

Split the oversized M100 2025 calculation-completeness manifest by keeping
manifest metadata in `completeness-manifest.toml` and moving the repeated
casilla entries into four `completeness/` fragments. The split is mechanical
and preserves the original casilla block order.

The file-size gate then exposed one overlong M303 TOML row. Wrapped the
existing `legal_refs` array without changing values.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_loader.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

All checks passed. Committed-registry and cross-revision tests emitted the
existing M347 semantic-role singleton warnings.

## Notes

A broader `ruff check src/aeat/domain/calculations/registry` run still fails on
pre-existing lint debt outside the authored files. The touched-file ruff gate
passed.
