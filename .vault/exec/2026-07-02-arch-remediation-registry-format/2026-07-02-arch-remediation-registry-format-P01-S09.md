---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:17219eba465d4a89a3746f16b1fc2e214b30e9fc762649917b090b69c05b5610'
step_id: 'S09'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Migrate modelo 231 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator

## Scope

- `src/aeat/_data/registry/aeat/modelos/231`

## Description

- Lift the four inline array-table fields (`casillas`, `workbook_parity_refs`, `application_links`, `filing_schedules`) verbatim out of the 231 `2021-y-siguientes` `revision.toml` into per-field fragment files, leaving only scalar metadata inline.

## Files

- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/casillas/0001-casillas.toml`
- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/workbook_parity_refs/0001-workbook_parity_refs.toml`
- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/application_links/0001-application_links.toml`
- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/filing_schedules/0001-filing_schedules.toml`

## Outcome

Behaviour preserved: the compiled-schema equality gate confirms the fragmented `ModeloRevision` is identical to the pre-migration inline shape; the loader directory-mode reviewability/inventory/schema-owned gates and the committed-registry + authority validation suites stay green.

## Notes

Purely mechanical authoring-surface move; no calc content changed.
