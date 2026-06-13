---
tags:
  - '#exec'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-plan]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-130-calc-verify` phase-1 step-3: extractor + generator + integration

Phase-1 step-3 of issue `#321` extended the synthetic generator and
the declaración extractor to the full 19-casilla liquidación block
and added the optional 4th integration test case.

## Files created

- `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md` — per-year rule-delta
  manifest with BOE citations + the L1 public-anchor waiver.

## Files modified

- `src/aeat/adapters/inbound/declaracion/_extractors/modelo_130_v2025.py` — extended
  `_MODELO_130_CASILLAS` from 7 to 19 ids. The label-regex map is
  built from this tuple, so casillas 08-19 now get parseable
  patterns. `_REQUIRED_FOR_COMPLETE` is **explicitly** set to the
  MVP-7 frozenset rather than derived from `_MODELO_130_CASILLAS`,
  so casillas 08-19 are *parseable but not required*: a real
  Modelo 130 declaración with no agraria activity (Apartado II
  blank) still surfaces `COMPLETE` extraction status.
- `tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_130_generator.py` —
  extended `_MODELO_130_BOXES` from 7 to 19 entries. Casillas 08-19
  occupy y_mm=140..250 with a 10 mm vertical pitch on the same A4
  page. Existing 7-casilla generator-callers preserve the same
  output for boxes 01-07; missing values for 08-19 still render
  label-only lines (the `draw_casilla_box` helper handles
  `value=None`).
- `src/aeat/adapters/inbound/declaracion/test_modelo_130_v2025.py` — added
  `test_full_19_casilla_liquidacion_round_trip` exercising the
  generator → PDF parse → ground-truth equality on all 19 casillas
  with non-zero asymmetric values (mirrors the operand-swap rich
  fixture; surfaces regex collisions as value mismatches rather
  than missing warnings).
- `tests/integration/test_kent_workflows.py` — extended the
  `_synth_modelo_130_pdf` defaults to all 19 casillas (zeros for
  08-19 plus arithmetic-consistent suma/parcial values). Existing 3
  mandatory cases preserved unchanged.
- `tests/integration/test_kent_workflows.py` — added the optional
  4th case `test_discrepancy_classified_correctly` to
  `TestKentImportsModelo130Declaracion`. Generates a PDF where
  casilla 04 prints 1 800,00 € while the engine re-derives 2 000,00 €
  (200,00 € drift). Asserts on stable substrings (status marker
  `NEEDS_REVIEW`, casilla id `04`, cause token
  `CORRECTNESS_DIVERGENCE`). Forward-compatible with future
  envelope evolution.

## Tests added

- 1 new case in `src/aeat/adapters/inbound/declaracion/test_modelo_130_v2025.py`.
- 1 new case in
  `tests/integration/test_kent_workflows.py::TestKentImportsModelo130Declaracion`.

All green.

## Round-trip evidence

`generate(params)` for a 19-casilla `Modelo130GenParams` produces
PDF bytes; `parse_declaracion(pdf_path)` returns a
`DeclaracionFiling` with 19 `ExtractedCasilla` entries and zero
warnings (`extraction_status is COMPLETE`).
`verify_declaracion(filing, ruleset=MODELO_130_2025)` returns
`VerificationStatus.VERIFIED` on a consistent fixture; mutating any
single computed casilla above the audit tolerance surfaces a
`CORRECTNESS_DIVERGENCE` discrepancy with the casilla id pinned.

## L1 anchor decision

Documented in `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md` § L1
public-anchor waiver. AEAT does not publish any specimen Modelo 130
declaración as a normative exemplar; the Tier-L bar is met via the
L3 synthetic round-trip rather than a hash-pinned real PDF. Two
trigger conditions for the waiver's expiry are listed.
