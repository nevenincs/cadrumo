---
tags:
  - '#plan'
  - '#registry-m100-row-width-deferrals'
date: '2026-06-04'
modified: '2026-06-04'
tier: L1
related:
  - '[[2026-06-04-registry-m100-row-width-deferrals-adr]]'
  - '[[2026-06-04-registry-m100-row-width-deferrals-research]]'
  - '[[2026-06-04-registry-row-width-pressure-plan]]'
  - '[[2026-06-04-registry-row-width-pressure-audit]]'
---


# `registry-m100-row-width-deferrals` `implementation` plan

Close the M100-specific row-width deferrals left by the completed row-width
pressure plan.

- [x] `S01` - Audit clean M100 deferred row-width targets and unrelated dirty M100 files; `.vault/audit`.
- [x] `S02` - Wrap M100 2021-2024 completeness-manifest `legal_refs` arrays without changing TOML values; `src/aeat/_data/registry/aeat/modelos/100/revisions`.
- [x] `S03` - Convert the M100 2020 inline `constraints` row to an equivalent nested TOML table with loaded M100 equality proof; `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/casillas/0146-0153.toml`.
- [x] `S04` - Tighten the TOML row-width baseline if the post-format corpus permits; `src/aeat/domain/calculations/registry/test_registry_reviewability.py`.
- [x] `S05` - Verify registry reviewability, loader, committed registry, and plan gates; `src/aeat/domain/calculations/registry`.
- [x] `S06` - Review and close the M100 row-width deferral slice; `.vault/audit`.
## Description

The row-width pressure plan reduced the registry TOML row baseline to 555
characters and documented five remaining M100 rows at or above 540 characters.
This plan handles only those deferred M100 rows. It does not authorise
legal-reference edits, source-reference edits, schema changes, loader changes,
or edits to unrelated dirty M100 completeness fragments.

## Steps

## Parallelization

S01 must land first. S02 and S03 are disjoint data edits but should run in
order so M100 equality checks are easy to review. S04 follows the post-format
inventory. S05 and S06 close the slice.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-m100-row-width-deferrals-plan.md`
