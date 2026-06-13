---
tags:
  - '#plan'
  - '#registry-construct-pressure'
date: '2026-06-03'
modified: '2026-06-03'
tier: L2
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-fragment-headroom-post-splits-audit]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
  - '[[2026-06-04-registry-construct-pressure-adr]]'
  - '[[2026-06-04-registry-construct-pressure-research]]'
---

# `registry-construct-pressure` `M200 construct fragment pressure follow-up` plan

### Phase `P01` - M200 construct pressure audit

Confirm the remaining M200 construct pressure shape before moving any registry data.

- [x] `P01.S01` - Audit M200 construct fragment split boundaries; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records`.

### Phase `P02` - M200 construct pressure split

Split only confirmed construct pressure using existing generic fragment merge semantics.

- [x] `P02.S02` - Split M200 constructs part 002 if audit confirms safe boundaries; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records`.

### Phase `P03` - Post-split headroom verification

Re-measure the registry corpus and close the pressure slice with tests and vault evidence.

- [x] `P03.S03` - Re-run construct-pressure corpus headroom audit; `.vault/audit`.

## Description

This continuation plan follows the completed registry-hardening next-work plan
and the post-split headroom audit. The only remaining TOML file above the
1,200-line pressure band is M200 `records/constructs.part-002.toml`, so this
plan targets that substrate only. It does not author new loader, schema, or
modelo-specific semantics; all splits must use the existing generic fragment
architecture.

## Steps

The Step rows above are the executable scope. Each Step must land as its own
commit with an exec record and code-review audit.

## Parallelization

The phases are sequential. S02 depends on the S01 boundary audit. S03 depends
on either an S02 split or an explicit S02 no-split decision.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_reviewability_baseline_remains_well_below_hard_cap -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-03-registry-construct-pressure-plan.md`
