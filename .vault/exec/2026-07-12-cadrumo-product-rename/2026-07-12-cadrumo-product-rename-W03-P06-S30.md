---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:79096d47766b49657d8e15fdcf006c0f0868de47f9eba84fcd8d6c054434370b'
step_id: 'S30'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget manuals build mapping and plugin name to cadrumo_data

## Scope

- `packaging/cadrumo_data_manuals/hatch_build.py`

## Description

- Reconcile the build-hook implementation already delivered by `f99ee0c821`.
- Verify the source-tree and embedded-sdist lookup roots use Cadrumo paths.
- Build the manuals companion wheel through the real Hatch custom hook.
- Inspect every archive member for namespace, owned-partition, and former-identity residue.

## Outcome

The build hook targets `cadrumo_data/_data/corpus`, declares the
`cadrumo-data-manuals-corpus` plugin identity, and resolves source content from
`src/cadrumo/_data/corpus` or the embedded `cadrumo_data` tree. The real wheel
contains 14 payload members, all beneath
`cadrumo_data/_data/corpus/manuals/`; no payload member uses `aeat_data` or falls
outside the manuals partition.

## Notes

This was an evidence-only closure because `f99ee0c821` overtook the implementation.
The hook retains `aeat_official` only when describing the sibling's official AEAT
corpus subtree, which is authority-owned semantics rather than a product namespace.
The shared two-wheel distribution gate remains assigned to S35 and was not edited.
