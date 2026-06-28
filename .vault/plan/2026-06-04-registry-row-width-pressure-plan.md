---
tags:
  - '#plan'
  - '#registry-row-width-pressure'
date: '2026-06-04'
modified: '2026-06-04'
tier: L2
related:
  - '[[2026-06-04-registry-reviewability-pressure-plan]]'
  - '[[2026-06-04-registry-reviewability-pressure-code-review-audit]]'
  - '[[2026-06-04-registry-row-width-pressure-adr]]'
  - '[[2026-06-04-registry-row-width-pressure-research]]'
---


# `registry-row-width-pressure` `implementation` plan

Reduce committed registry TOML row-width pressure after the M123 line-count
split made row length the next active reviewability risk.

### Phase `P01` - row-width inventory

Classify every committed registry TOML row near the current row-width baseline
before editing data files.

- [x] `P01.S01` - Audit registry TOML rows at or above 540 characters and classify clean edit targets versus concurrent dirty deferrals; `.vault/audit`.

### Phase `P02` - value-preserving formatting

Mechanically reformat only clean TOML rows, preserving parsed registry values
and loaded modelo objects.

- [x] `P02.S02` - Reformat clean near-threshold M100 casilla TOML rows without changing TOML values; `src/aeat/_data/registry/aeat/modelos/100`.
- [x] `P02.S03` - Reformat clean non-M100 near-threshold TOML rows if S01 authorises them; `src/aeat/_data/registry/aeat/modelos`.
- [x] `P02.S04` - Defer dirty concurrent near-threshold TOML rows with exact paths and owners; `.vault/audit`.
- [x] `P02.S05` - Tighten the reviewability row-width baseline only as far as the post-format corpus permits; `src/aeat/domain/calculations/registry/test_registry_reviewability.py`.

### Phase `P03` - verification and review

Verify value preservation and close the row-width pressure slice.

- [x] `P03.S06` - Verify loader, reviewability, committed registry, record-design, drift, and plan gates for row-width repairs; `src/aeat/domain/calculations/registry`.
- [x] `P03.S07` - Review the row-width pressure slice and persist closure artefacts; `.vault/audit`.

## Description

The prior reviewability-pressure plan reduced M123 line-count pressure and
tightened the TOML line-count baseline. It deliberately left row-width
pressure open because M100 still had a 572-character row against a
575-character baseline. This plan addresses that next substrate using
value-preserving TOML formatting only. It does not authorise legal-reference
changes, source-reference changes, schema changes, loader changes, or edits to
dirty concurrent paths.

## Steps

## Parallelization

P01 must land first. P02.S02 and P02.S03 may run independently only if their
target files are clean and disjoint. P02.S04 must record any dirty-path
deferral before P02.S05 tightens gates. P03 closes the plan after all
formatting and deferrals are committed.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_record_design.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-row-width-pressure-plan.md`
