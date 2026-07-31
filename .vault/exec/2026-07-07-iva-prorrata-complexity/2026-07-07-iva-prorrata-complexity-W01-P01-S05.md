---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-17'
body_hash: 'sha256:50197057a9366b39b0644a562cf015dadaf755bf74c0a839185d651de1f9a8d3'
step_id: 'S05'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Verify the exclusion classification against an AEAT worked example with no hand-computed expected values

## Scope

- `src/aeat/application/calculations/tests/`

## Description

- Add an AEAT-grounded oracle test for the art-104.Tres exclusion, reading the expected figures from the bundled AEAT Manual practico IVA 2025 prorrata-general oracle (`modelo-303-prorrata-general-regularizacion.json`, pages 137-138): con-derecho 25.000, total 45.000, definitiva 56%.
- Augment the manual example with a one-off non-habitual inmueble sale (art-104.Tres 4a) and prove the exclusion-filtered ledger rollup removes it from both terms, reproducing the manual's 25.000 / 45.000 volumes and hence the manual's 56% via `compute_prorrata_definitiva_anual`.
- Add an anti-tautology companion proving the exclusion is load-bearing: without it the con-derecho volume inflates and the percentage is not the manual's 56%.

## Outcome

- Modified files: `src/aeat/application/calculations/tests/test_prorrata_art104_tres_exclusion_oracle.py` (new).
- 2 tests pass; ruff / ruff-format / ty clean.
- Every expected value is read from the bundled manual oracle; none is derived from the formula under test.
- Committed as `b0cd2ad74b`.

## Notes

- The bundled AEAT Manual IVA prorrata example does not itself carry an art-104.Tres excluded operation, and no other bundled AEAT example does, so the manual example is augmented with one to exercise the exclusion - the expected percentage/volumes remain the manual's literal figures because the added operation is lawfully excluded from both terms. This grounds the verification in the real AEAT figure rather than fabricating one.
