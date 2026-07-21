---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S35'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update real-wheel companion partition and namespace invariants

## Scope

- `dev/packaging/tests/test_cadrumo_data_distribution.py`

## Description

- Reconcile the already-renamed test module with the live Cadrumo companion projects and prior S29-S34 evidence.
- Retarget tracked source discovery, project directories, distribution names, wheel globs, and archive prefixes to Cadrumo.
- Build both real wheels into pytest-owned temporary directories and compare their members against independent Git-tracked source evidence.
- Preserve `aeat_official` solely as the official authority corpus partition and remove former product compatibility assumptions.
- Correct the direct module-name reference in the root wheel-boundary test.

## Outcome

The gate builds `cadrumo-data-manuals` and `cadrumo-data-official` from their canonical project directories and validates their shared `cadrumo_data` PEP 420 namespace. It derives the expected payload from tracked `src/cadrumo/_data/corpus` binaries, proves each wheel exactly owns its declared partition, proves the wheels are disjoint and exhaustive together, rejects namespace initializers and derived/foreign members, pins both versions to the root distribution, and enforces the PyPI file cap.

All five real-wheel tests passed. Ruff, canonical-test formatting, former-identity residue, direct-reference residue, and scoped diff checks passed.

## Notes

Commit `f99ee0c821` had already renamed the test filename but left its implementation on former project and namespace values. The direct-reference file has unrelated pre-existing formatter drift; this Step changes only its stale test-module name and does not reformat or rewrite that broader wheel test.

Formal review found no issue and confirmed the evidence is independent, non-tautological, alias-free, workspace-safe, and faithful to the production hook partitions.
