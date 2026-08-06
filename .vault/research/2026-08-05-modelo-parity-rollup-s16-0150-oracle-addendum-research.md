---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:97e1211e88d11c351dfd5c7cbe3f8c9191c08f3ca7281130b33b5366905344a5'
related:
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-candidate-contract-matrix-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-evidence-research]]'
  - '[[2026-08-05-modelo-parity-rollup-semantic-decision-boundary-audit]]'
  - '[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]'
  - '[[2026-08-05-modelo-parity-rollup-plan]]'
---
# `modelo-parity-rollup` research: `S16 0150 rental oracle addendum`

## Decision boundary

The 2025 `0150` row must remain manual/open. No honest independent 2025 oracle can currently run from persisted fincas state through the existing aggregate because the source model cannot represent the bundled official worked example without precomputing values or misusing fields.

## Findings

### Persisted rental source is not calculation-ready

The official 2025 rental worked example requires a furniture-amortization amount of `388.13` and nine-of-twelve month allocation of expenses and amortization, producing total deductible expenses of `2,562.91` and a `2,958.38` reduction. The bundled evidence locator is `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:12794`.

The persisted rental model does not contain the required facts. `FincaRendimientoRecord` exposes gross rent and `dias_alquilados`, while `FincaAmortizacionLedgerEntry` represents the building amortization ledger; it has no separate furniture-amortization evidence. The aggregate path prorates building amortization by integer days but consumes expense records without contract-period allocation. Grounding locations: `src/cadrumo/domain/fincas/_models.py:225`, `src/cadrumo/domain/fincas/_models.py:277`, and `src/cadrumo/domain/fincas/_aggregates.py:267-317`.

The aggregate also returns a total `reduccion_arrendamiento_vivienda` plus attribution maps, not the repeated per-inmueble/per-contract filing rows required to claim that one aggregate is casilla `0150`. `fincas_source_readiness()` independently reports that the source is not enrolled through the canonical secure-storage boundary: `src/cadrumo/domain/fincas/_source_readiness.py:34`.

### Oracle attempt

The Luna Max worker was instructed to create only a real repository-backed test at `src/cadrumo/domain/fincas/tests/test_modelo_100_2025_rental_oracle.py`. It created no file because the current model could not represent the authoritative example without fabricating furniture or period-allocation facts. No pytest, Ruff, format, or basedpyright result is claimed for this absent artifact.

This is a positive audit result: the missing source contract is measured rather than hidden behind a synthetic aggregate fixture.

## Sources

- VaultSpec RAG result for the official rental worked example: `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:12794`.
- Persisted income model: `src/cadrumo/domain/fincas/_models.py:225`.
- Persisted amortization model: `src/cadrumo/domain/fincas/_models.py:277`.
- Aggregate implementation: `src/cadrumo/domain/fincas/_aggregates.py:267-317`.
- Source-readiness boundary: `src/cadrumo/domain/fincas/_source_readiness.py:34`.
- Accepted parity contract and prior decision boundary: `.vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md` and `.vault/audit/2026-08-05-modelo-parity-rollup-semantic-decision-boundary-audit.md`.

## Required implementation gates

Before SOL can authorize a 2025 producer, the source contract must add:

- versioned persisted furniture-amortization evidence and its provenance;
- per-contract period allocation for income, expenses, and amortization, including start/termination boundaries;
- a typed enrolled calculation source crossing secure storage;
- explicit per-inmueble/per-contract allocation to repeated `0150`, including qualification, negative yields, rounding, and carry-forward semantics;
- a structured official oracle reproducing `2,958.38` and the zero-reduction case through the real secure-storage-to-calculate path;
- one producer mechanism with formula/binding/casilla reverse wiring.

Until those gates exist, cloning the 2024 `0150` formula or adding an aggregate binding would be an ungrounded semantic change.
