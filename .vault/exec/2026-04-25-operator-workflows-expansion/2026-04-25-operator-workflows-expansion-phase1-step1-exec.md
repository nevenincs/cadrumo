---
tags:
  - '#exec'
  - '#operator-workflows-expansion'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-operator-workflows-expansion-plan]]"
  - "[[2026-04-25-operator-workflows-expansion-adr]]"
---

# `operator-workflows-expansion` exec phase1 step1: implementation

Implementation step record for issue wgergely/aeat#340.

## Files modified

- `tests/integration/test_kent_workflows.py` - 10 new test classes
  added (Modelos 100-summary / 111 / 115 / 123 / 131 / 180 / 200 / 202
  / 303 / 390); module imports extended; helpers
  `_synth_quarterly_pdf`, `_synth_annual_pdf`, `_synth_modelo_303_pdf`,
  `_synth_modelo_100_summary_pdf`, `_partial_subset` introduced; per-
  modelo label maps + happy-path values inlined.
- `docs/coverage/modelos.md` - new "kent CLI integration coverage"
  section + provenance refresh.

No source changes under `src/aeat/`.

## Test classes added

Each class follows the Modelo 130 template at line 116 (3 mandatory
cases + 1 optional discrepancy case for ruleset-bearing modelos):

| Class                                          | CLI flag             | Cases | Notes                                |
| ---------------------------------------------- | -------------------- | ----- | ------------------------------------ |
| TestKentImportsModelo111Declaracion            | --from-declaracion   | 4     | 19% withholding formulas             |
| TestKentImportsModelo115Declaracion            | --from-declaracion   | 4     | arrendamientos urbanos               |
| TestKentImportsModelo123Declaracion            | --from-declaracion   | 4     | aggregation chain                    |
| TestKentImportsModelo131Declaracion            | --from-declaracion   | 4     | modulos chain (6 computed)           |
| TestKentImportsModelo180Declaracion            | --from-declaracion   | 4     | annual resumen                       |
| TestKentImportsModelo200Declaracion            | --from-declaracion   | 3     | locks in UNVERIFIABLE; 4th omitted   |
| TestKentImportsModelo202Declaracion            | --from-declaracion   | 4     | IS pago fraccionado                  |
| TestKentImportsModelo303Declaracion            | --from-declaracion   | 4     | dedicated 303 generator (33 cas)     |
| TestKentImportsModelo390Declaracion            | --from-declaracion   | 4     | annual IVA                           |
| TestKentImportsModelo100SummaryBorrador        | --from-borrador      | 3     | happy-en + happy-es + discrepancy-via-drift (no `Extraction status:` on this CLI path) |

Total new tests: 38.

## Year choices

Every modelo tests at 2025 - the only landed year for the registered
extractor. Modelo 200 explicitly locks in UNVERIFIABLE because the
2025 extractor + 2024-only ruleset emit that verdict.

## Module-level marker preserved

`pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input,
pytest.mark.fixture_tier_l3]` unchanged (pre-existing markers
preserved per ADR D8).

## Synthetic fixture status

No new generators authored. All ten classes consume the existing
`_generic_quarterly_generator.py`, `modelo_100_generator.py`, and
`modelo_303_generator.py`. Per-modelo label maps were inlined in the
test file (mirroring `aeat.adapters.inbound.declaracion.test_quarterly_extractors`).

## Local gates

- `just lint` - pass (after replacing `x` MULTIPLICATION SIGN with
  ASCII `x` in 9 docstrings + 1 comment, and ruff isort split
  multi-import statements).
- `just typecheck` - pass.
- `just test` - 44 tests in `tests/integration/test_kent_workflows.py`
  pass. Full suite TBD.
- Coverage gate TBD.
- `just hooks` TBD.
