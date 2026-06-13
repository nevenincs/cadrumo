---
tags:
  - '#reference'
  - '#modelo-390-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-390-rule-delta-reference]]"
  - "[[2026-04-27-modelo-390-calc-verify-research]]"
  - "[[2026-04-27-modelo-390-calc-verify-adr]]"
---

# Modelo 390 L1 public-anchor waiver

## Decision

No L1 public declaration PDF is hash-pinned for Modelo 390 in issue `#327`.

## Rationale

Modelo 390 declarations are taxpayer-specific autoliquidaciones. A real filed declaración-resumen anual contains private NIF, period, and full-year liquidation data. Public BOE/AEAT instruction PDFs and form templates are legal or layout references, but they are not the same artefact as a completed declaration PDF and would not validate the extractor's real declaration path.

The project therefore uses L3 synthetic PDFs as the executable fixture tier for this issue. The synthetic Modelo 390 generator emits the 15-casilla scoped surface, the extractor parses those casillas, and Kent workflow integration verifies the generated declaration through the same CLI path used by the application.

## Replacement Evidence

The waiver is compensated by:

- 15 casillas rendered by the synthetic Modelo 390 generator covering Apartado 1 datos estadísticos, Apartado 3 régimen general anual, Apartados 4-5 otros regímenes, Apartado 6 resultado anual, Apartado 7 regularización bienes inversión;
- `Modelo390V2024Extractor`, `Modelo390V2025Extractor`, and `Modelo390V2026Extractor` round-trip tests;
- Kent CLI integration coverage for English happy-path, Spanish-default happy-path, partial extraction, and classified discrepancy cases;
- BOE legal citations on every computed casilla;
- Cumulation tests asserting that an annual Modelo 390 fixture round-trips against four synthetic quarterly Modelo 303 fixtures (`test_modelo_390_cumulation.py`).

## Revisit Triggers

Replace this waiver if AEAT publishes a non-private completed Modelo 390 declaration exemplar or a contributor provides an explicitly consented, scrubbed, hash-pinned declaration PDF that satisfies the project's privacy discipline.
