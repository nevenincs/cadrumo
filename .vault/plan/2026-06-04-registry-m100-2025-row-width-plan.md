---
tags:
  - '#plan'
  - '#registry-m100-2025-row-width'
date: '2026-06-04'
modified: '2026-06-04'
tier: L1
related:
  - '[[2026-06-04-registry-m100-2025-row-width-adr]]'
  - '[[2026-06-04-registry-m100-2025-row-width-research]]'
  - '[[2026-06-04-registry-m100-row-width-deferrals-plan]]'
---

# `registry-m100-2025-row-width` `implementation` plan

Reduce the remaining M100 2025 TOML row-width pressure above 520 characters.

- [x] `S01` - Audit clean M100 2025 rows above 520 characters and dirty-path exclusions; `.vault/audit`.
- [x] `S02` - Wrap the four M100 2025 `legal_refs` rows above 520 characters without changing TOML values; `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas`.
- [x] `S03` - Tighten the TOML row-width baseline if the post-format corpus permits; `src/aeat/domain/calculations/registry/test_registry_reviewability.py`.
- [x] `S04` - Verify reviewability, committed registry, loader, and plan gates; `src/aeat/domain/calculations/registry`.
- [x] `S05` - Review and close the M100 2025 row-width slice; `.vault/audit`.
## Description

The previous M100 deferral slice lowered the reviewability baseline to 530 and
left four M100 2025 `legal_refs` rows at 526-528 characters. This plan handles
only those clean rows and does not authorise legal-reference edits,
source-reference edits, schema changes, loader changes, or edits to unrelated
dirty M100 completeness fragments.

## Steps

## Parallelization

S01 must land first. S02 and S03 must run in order so the baseline follows the
post-format corpus. S04 and S05 close the slice.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-m100-2025-row-width-plan.md`
