---
tags:
  - '#exec'
  - '#modelo-123-calc-verify'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S-aitor-211'
related:
  - '[[2026-04-27-modelo-123-calc-verify-plan]]'
---

# `modelo-123-calc-verify` Aitor #211 — M123 casilla 06 arithmetic oracle

Locked M123 casilla 06 formula correctness with four oracle tests and fixed
two peer-agent legal-catalogue regressions that blocked the full registry
test suite.

- Modified: `src/aeat/domain/calculations/registry/test_modelo_123_registry.py`
- Modified: `src/aeat/_data/registry/aeat/legal/irpf.toml`

## Description

Task #211 alleged casilla 06 returned `nperceptores + base` (42007) instead
of `base` (42000). Investigation confirmed both M123 revisions already carry
correct formulas:

- 2024+ revision: `modelo-123-total-base` = `[04] + [05]` (base_dividendos + base_resto)
- 2019-2023 revision: `modelo-123-2019-total-liquidacion` = `[03-legacy] + [05-legacy]` (retenciones + regularizacion)

Neither formula references the perceptor-count casillas (01, 02). The
deliverable was therefore a suite of oracle tests that lock in this
invariant and would catch any future regression where perceptor counts
leak into the base computation.

Two peer-agent regressions were also fixed to unblock the registry test
suite. The `irpf.toml` entries for `ley-35-2006:art-84` and
`ley-35-2006:art-7-h` were added by a concurrent agent with `required_text`
arrays containing strings absent from the corpus. The arrays were corrected
to match text actually present in `corpus/normatives/html/ley-35-2006.html`.

## Tests

Four new oracle tests added to `test_modelo_123_registry.py`:

- `test_m123_casilla_06_equals_base_dividendos_plus_base_resto`: nperceptores=7
  (01=4, 02=3), base=42000 in casilla 04. Asserts casilla 06=42000.00 with
  precondition casilla 03=7. Fails at 42007 (the reported bug vector).

- `test_m123_casilla_06_base_resto_only`: nperceptores=1, base=5000 in casilla
  05. Asserts casilla 06=5000.00, not 5001. Catches perceptor-count leakage
  in the alternative input path.

- `test_m123_casilla_06_invariant_to_nperceptores`: anti-tautology proof —
  base fixed at 42000; nperceptores varied across 1, 7, 100. All three must
  return casilla 06=42000.00. Fails if any perceptor-count operand is added.

- `test_m123_legacy_casilla_06_invariant_to_nperceptores_and_base`: 2019-2023
  revision (filing_year=2022); 01-legacy=7, 02-legacy=42000, 03-legacy=100,
  05-legacy=0. Asserts casilla 06-legacy=100.00 (retenciones+regularizacion
  only). Confirms the legacy formula is also free of perceptor/base leakage.

All 6 tests pass: `6 passed in 33.18s`.
