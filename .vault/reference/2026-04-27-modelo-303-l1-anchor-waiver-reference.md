---
tags:
  - '#reference'
  - '#modelo-303-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-303-rule-delta-reference]]"
  - "[[2026-04-27-modelo-303-calc-verify-research]]"
  - "[[2026-04-27-modelo-303-calc-verify-adr]]"
---

# Modelo 303 L1 public-anchor waiver

## Decision

No L1 public declaration PDF is hash-pinned for Modelo 303 in issue `#326`.

## Rationale

Modelo 303 declarations are taxpayer-specific autoliquidaciones. A real filed declaration normally contains private NIF, period, and filing-result data. Public BOE/AEAT instruction PDFs and form templates are legal or layout references, but they are not the same artefact as a completed declaration PDF and would not validate the extractor's real declaration path.

The project therefore uses L3 synthetic PDFs as the executable fixture tier for this issue. The synthetic Modelo 303 generator emits all 33 liquidación casillas, the extractor parses those casillas, and Kent workflow integration verifies the generated declaration through the same CLI path used by the application.

## Replacement Evidence

The waiver is compensated by:

- all 33 casillas rendered by the synthetic Modelo 303 generator;
- `Modelo303V2025Extractor` and `Modelo303V2026Extractor` round-trip tests;
- Kent CLI integration coverage for English, Spanish-default, partial extraction, 2026 happy path, and classified discrepancy cases;
- BOE legal citations on every computed casilla.

## Revisit Triggers

Replace this waiver if AEAT publishes a non-private completed Modelo 303 declaration exemplar or a contributor provides an explicitly consented, scrubbed, hash-pinned declaration PDF that satisfies the project's privacy discipline.
