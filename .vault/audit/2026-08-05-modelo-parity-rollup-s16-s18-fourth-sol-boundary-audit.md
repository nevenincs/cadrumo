---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:7b6bdca7aee5994c85d5f4f108e7bf912939a839bf3c65f070f94d22490a3a76'
related:
  - "[[2026-08-05-modelo-parity-rollup-s16-source-contract-research]]"
  - "[[2026-08-05-modelo-parity-rollup-s17-0613-cap-rounding-research]]"
  - "[[2026-08-05-modelo-parity-rollup-s18-1481-oracle-addendum-research]]"
---
# `modelo-parity-rollup` audit: `S16 S17 S18 fourth SOL authorization boundary`

## Scope

Review the latest SOL adjudication, the RAG-grounded S16 source-contract addendum, the S17 cap/rounding evidence, and the S18 activity/layout evidence after reopening the three deferred M100/2025 rows. The audit distinguishes authorized evidence work from prohibited producer promotion and reconciles the VaultSpec plan state.

## Findings

### s16-source-contract | high | 0150 remains manual because the source contract is incomplete

S16 production promotion is deferred. The current `FincaRendimientoRecord` carries contract income and days, `FincaGasto` carries finca/year/category amounts, and `FincaAmortizacionLedgerEntry` is a building-specific cumulative ledger (`src/cadrumo/domain/fincas/_models.py:225-311`). The 2025 official worked example requires separate furniture amortization and explicit period allocation (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:12833`). `fincas_source_readiness()` remains false because these aggregates do not cross canonical secure storage (`src/cadrumo/domain/fincas/_source_readiness.py:34-52`).

### s17-cap-oracle | high | 0613 lacks an executable 2025 rounding contract

S17 production promotion is deferred. The official 2025 evidence establishes per-child qualifying months and effective non-subsidized spend, with official 2-month and 6-month examples at `source.pdf.extracted.md:54989-55004` and `:55073-55088`. The 7/8/12-month observations still do not identify one executable rounding stage. The current profile has raw annual/monthly spend but no versioned per-child effective-spend and cap result, and the 2025 casilla remains manual (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0194-c0613.toml:1-8`).

### s18-annual-engine | high | 1481 cannot be populated by copying M131 casilla 01

S18 production promotion is deferred. The 2025 official declaration dictionary distinguishes repeated activity-level `E4AR` casilla `1481` from result-level `E4SUMA` casilla `1482` and `E4TOTAL` casilla `1484` (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:369-374`). The real M131 activity oracle proves shared-engine activity identity but not an M100 transfer. SOL therefore rejects a copied 2024 relation and any four-quarter sum of already activity-collapsed M131 casilla `01`.

### production-boundary | critical | No production files are authorized by the adjudication

S16 allows only a focused source-contract ADR/research and oracle acquisition. S17 allows only evidence/oracle completion. S18 allows only annual shared-engine mapping research/oracle work. The allowed production-file set is empty: no M100 casilla, formula, binding, relation, profile schema, fincas model, aggregate, source resolver, or readiness flag may be changed.

### plan-tracking | medium | Deferred adjudication rows are now represented honestly

The plan reopens S16, S17, and S18. W06 adds S29 for S16 contract research/proposed ADR, S30 for the S17 independent oracle matrix, and S31 for the S18 annual mapping evidence. S31 is checked only as an evidence tranche; S18 remains open. The current plan status is 26 of 31 steps completed with no missing execution IDs.

## Recommendations

- Keep S16, S17, and S18 open and retain the 2025 manual declarations.
- Obtain explicit user approval before accepting the proposed S16 source-contract ADR; the ADR must not become an implicit decision through research prose.
- Complete S17 with authoritative independent expected values for 0, 2, 6, 7, 8, and 12 qualifying months, effective-spend reductions, turning-three behavior, and unequal per-child caps.
- Complete S18 through the shared annual activity engine, with independent M100 values for multiple activities and repeated `1481` rows, rather than an M131 casilla-01 relation.
- Re-run SOL per row after its evidence gate closes. Passing prerequisite tests must remain visibly distinct from M100 parity certification.
