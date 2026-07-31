---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:c21b354418691904edc9fa550569f885ab2a9fd80df7f8459bde3dc780979baf'
step_id: 'S10'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Migrate modelo 361 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator

## Scope

- `src/aeat/_data/registry/aeat/modelos/361`

## Description

- Lift the five inline array-table fields (`casillas`, `workbook_parity_refs`, `application_links`, `deadline_windows`, `filing_schedules`) out of the 361 `2010-y-siguientes` `revision.toml` into per-field fragment files, leaving only scalar metadata inline.

## Files

- `src/aeat/_data/registry/aeat/modelos/361/revisions/2010-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/361/revisions/2010-y-siguientes/{casillas,workbook_parity_refs,application_links,deadline_windows,filing_schedules}/0001-*.toml`

## Outcome

Behaviour preserved: standalone equality verification confirms the fragmented `ModeloRevision` is byte-identical to the pre-migration inline baseline, and a full `load_registry_tree` over the whole registry compiles clean (39 modelos, 449 legal refs). Residual inline array-tables in `revision.toml`: zero.

## Notes

The pytest conftest chain was transiently broken at execution time by unrelated live peer WIP (a peer-staged `aeat.domain.user_profile._registry_contract` imports `CasillaFieldKind` from the `aeat.domain.calculations` package before that campaign has exported it), so the equality gate was run via a standalone loader script that bypasses the poisoned conftest rather than through pytest. The registry loader import chain itself is unaffected.
