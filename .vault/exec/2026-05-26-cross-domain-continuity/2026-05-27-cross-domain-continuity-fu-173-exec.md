---
tags:
  - '#exec'
  - '#cross-domain-continuity'
step_id: "FU-173"
date: '2026-05-27'
modified: '2026-05-27'
commit: ab19ec10d
related: []
---

# FU-173 — layout_authority coverage fix for M151 / M714 / M721

## What was broken

`test_committed_registry_tree_has_required_model_law_coverage` failed because the
three stub models added in prior sessions (M151 Beckham, M714 Patrimonio, M721
crypto) each had only `official_source_guidance` sources in their legal catalogues.
The `_REQUIRED_COVERAGE_TIERS` gate also requires `layout_authority`, so the
`RegistryCoverageAudit.ok` check returned False for all three.

## Fix

Added new source entries with `evidence_tier = "layout_authority"` to each legal
TOML catalogue, reusing the same corpus HTML, sha256, and bytes as their paired
`form_spec` counterparts but carrying distinct IDs:

- `boe-modelo-151-layout` in `irpf-impatriados.toml`
- `boe-modelo-714-layout` in `patrimonio.toml`
- `boe-modelo-721-2023-layout` in `monedas-virtuales.toml`

Wired each new ID into the revision `source_refs` array:

- `src/aeat/_data/registry/aeat/modelos/151/revisions/2024-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/721/revisions/2023-y-siguientes/revision.toml`

## Verification

`test_committed_registry_tree_has_required_model_law_coverage` — 1/1 passed (40s).

## Commit

`ab19ec10d` — 6 files changed, 42 insertions
