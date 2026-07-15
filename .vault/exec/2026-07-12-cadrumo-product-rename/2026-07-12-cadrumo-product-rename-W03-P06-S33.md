---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S33'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget official build mapping and plugin name to cadrumo_data

## Scope

- `packaging/cadrumo_data_official/hatch_build.py`

## Description

- Inspect overtaking commit `f99ee0c821` and read the current official companion hook in full.
- Verify the source-tree and embedded-sdist roots, Cadrumo target namespace, plugin identity, and official/normative ownership partition.
- Build the real companion wheel and compare every payload member with the tracked owned corpus binaries.
- Preserve `aeat_official` as the external-authority corpus subtree while rejecting the former product namespace.

## Outcome

The overtaking implementation is correct and needs no tracked edit. The hook reads from `src/cadrumo/_data/corpus` or embedded `cadrumo_data`, writes beneath `cadrumo_data/_data/corpus`, registers plugin `cadrumo-data-official-corpus`, and owns exactly `aeat_official` plus `normatives`.

The real 0.1.1 wheel contains 177 payload members, exactly equal to the 177 tracked non-test PDF/XLS/XLSX binaries in those two source partitions. It contains no manuals payload, `aeat_data` namespace, or namespace initializer. Ruff, formatting, residue, and scoped diff checks passed.

## Notes

S33 is evidence-only because `f99ee0c821` already completed the hook cut. The combined packaging gate remains deferred to S35: its live constants still point to `packaging/aeat_data_*`, so all four wheel-backed cases error during setup and the version case fails before reaching hook behavior. The direct S33 wheel and tracked-source equality proof passed.

Formal review found no issue and independently confirmed the hook identities, exact partition, authority classification, artifact equality, and S35 deferral.
