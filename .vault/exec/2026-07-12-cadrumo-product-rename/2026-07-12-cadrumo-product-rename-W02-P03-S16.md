---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S16'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Preserve the authority registry taxonomy under the new product root

## Scope

- `src/cadrumo/_data/registry/aeat`

## Description

- Ground the bundled authority registry through semantic discovery, representative whole-file reads, and exact residue searches.
- Parse every bundled authority TOML document and confirm the product rename did not create a `registry/cadrumo` taxonomy.
- Compare the relocated registry against the S09 snapshot and normalize only the S12 Python callable-prefix substitution.
- Preserve the authority-owned `aeat` directory, identifiers, source references, URLs, and legal evidence without source edits.

## Outcome

The preservation boundary was already satisfied. All 16,273 TOML documents under the authority registry parsed successfully, and no product-named registry directory exists. Exact residue checks found no former `aeat.` Python targets in registry TOML while representative application links resolve through `cadrumo.` targets.

The complete S09-to-current diff covered 250 files with 621 removed and 621 added lines. Replacing only `cadrumo.` with `aeat.` in the current added lines made both line multisets identical, proving that the registry drift consists exclusively of the planned S12 callable retargeting. Authority taxonomy names, AEAT source identifiers, official URLs, and legal evidence remain preserved.

## Notes

No registry source defect was found, so no authority data was renamed or rewritten. A first per-blob comparison attempt was stopped after its process-per-file approach proved unnecessarily slow; the final complete Git diff normalization supplied equivalent whole-tree evidence efficiently.
