---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S67'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W08.P19.S67

Scope: production multiyear IVA compensation reconstruction from Modelo 303 period history plus Modelo 390 annual compensation evidence.

## Description

- Ground Modelo 390 compensation fields against official AEAT Modelo 390 guidance and registry casilla/source declarations.
- Add typed `IvaCompensationAnnualSummary` and `IvaCompensationAnnualCrossCheck` records for filed Modelo 390 annual evidence.
- Extract Modelo 390 casillas 97 and 662 from filed observations without treating 390 as a Modelo 303 period state.
- Cross-check the production Modelo 303 carry-forward report against the filed Modelo 390 annual summary.
- Correct Modelo 390 casilla 97 to source the last-period generated compensation amount, not the full end-of-period available balance.
- Project `iva.compensacion-generada-periodo` from secure IVA-history states so compensation bindings can resolve from filed-history evidence.
- Enroll the new translated error key through the `aeat.locales` CLI for `en`, `es`, `ca`, and `hu`.

## Outcome

S67 is satisfied for the current production-code slice. Modelo 303 filed observations still produce period states and carry-forward lots covering generation, application, remaining balance, and expiry review. Modelo 390 annual filed observations now produce separate annual summary evidence for casilla 97 and casilla 662, and the cross-check reports whether the 303 carry-forward projection matches the filed 390 annual compensation fields. Prior-year lots remain visible through expiry review, but they do not inflate the exercise-specific Modelo 390 97/662 comparison.

Official grounding used:

- `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-iva-2024/capitulo-09-declaraciones-informativas-iva-379/declaracion-resumen-anual-modelo-390/contenido-modelo-390.html`
- `https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G412/instr390.pdf?telegram=espanevo`
- `https://www.boe.es/biblioteca_juridica/codigos/abrir_pdf.php?fich=057_Impuesto_sobre_el_Valor_Anadido.pdf`

Verification passed:

- `python -m pytest -q src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py::test_modelo_390_annual_iva_pipeline_resolves_binding_chain_from_four_303_filings src/aeat/application/calculations/test_modelo_390_303_reconciliation_continuity.py`
- `python -m pytest -q src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_modelo_390_303_reconciliation_continuity.py`
- `python -m ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_modelo_390_303_reconciliation_continuity.py`
- `python -m ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/_binding_prefill.py src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py`
- `python -m aeat.locales audit`

## Notes

The post-implementation review found that a full Modelo 390 snapshot currently needs a clearer merge/provenance strategy when ordinary calculation observations and secure IVA-history observations both exist for the same Modelo 303 periods. That is now tracked on S68. No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
