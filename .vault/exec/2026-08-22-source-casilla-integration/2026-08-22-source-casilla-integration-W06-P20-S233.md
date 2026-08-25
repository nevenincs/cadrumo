---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:08cdb8824ade3fa72ceffabe31d961916bbe8173c269a9650de7632b48f6bb7b'
step_id: 'S233'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# After Modelo 194's 2019-2024 source eras are selected, determine whether any required external value lifecycle exists and add no source kind, binding, casilla, or census candidate until official fact-to-destination evidence settles it.

## Scope

- `.vault/research/`
- `src/cadrumo/_data/source_connectivity/census.toml`
- `src/cadrumo/_data/registry/aeat/modelos/194/`

## Description

- Used semantic discovery and exact repository searches across M194 registry, source-connectivity census, source mesh, withholding families, filing producers, export path, and official corpus.
- Re-fetched and hash-pinned the BOE XML versions for the 1999 approving order and the 2019, 2023, and 2024 amendments; verified the three enrolled AEAT record-design binaries.
- Confirmed the finite annual registry selection for `2019`, `2023`, and `2024`, retaining refusal for 2020--2022 and 2025 onward.
- Distinguished the type-1 declarant and repeatable type-2 perceptor filing record from pre-filing source acquisition, direct-manual summary input, design extraction, transport, and post-filing read surfaces.
- Compared the generic withholding source to M194 type-2 facts and confirmed that its M190/M193 contract cannot preserve M194 asset-operation fields, row identity, or sign/rounding semantics.
- Recorded the factual no-current-candidate boundary without adding a source kind, binding, casilla, resolver, export route, census row, or model-specific ADR.

## Outcome

S233 establishes an evidence-backed **no current source-connectivity candidate** for M194. The three official designs prove filing destinations and a repeated perceptor record, but do not identify a canonical source fact and holder, native acquisition grain, durable identity, capture provenance, absence/duplicate/correction semantics, or encrypted non-lossy owner. This is not a conclusion that M194 required facts are tax-inapplicable.

The five direct-manual `resumen` casillas `01`--`05` remain unchanged. The 2020--2022 and 2025-plus selector refusals remain governed by exact era evidence. AEAT file presentation, consultation/cancellation, record-design parsing, generic repeated-record transport, and the existing M190/M193 withholding path remain non-substitutable filing/read or distinct-source surfaces. No M194 source lifecycle or source-owned export is connected.

Reopen only after official/evidence-backed material identifies the canonical carrier and holder, native perceptor-operation grain and durable identity, encrypted non-lossy ingress with provenance plus absence/duplicate/correction semantics, and one selected-era type-1/type-2 destination map with aggregation/sign/unit/rounding rules. Any export work additionally needs separate producer, map, render, and generated-byte proof.

## Notes

- No model-specific ADR was created: the record-design evidence does not establish a source candidate whose ownership could be normatively deferred.
- The S232 independent review passed in `a3231576c5` before this step mutated the shared source plan/index lane.
- Focused M194 registry test file passed: 15 tests. Ruff passed for that file. Bounded Vault results are recorded with this step; no broad runtime suite was run.
