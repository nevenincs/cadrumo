---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:31710a17de2ffb18ab2f2fcea9853d92324740923f8d5115be703463f751459c'
step_id: 'S13'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Emit the settlement art-103.Dos.2 +10% mandatory-especial advisory Notice via is_especial_mandatory, non-blocking, both totals on Notice.context

## Scope

- `src/aeat/application/calculations/_prorrata_regularizacion.py`

## Description

- Add `build_prorrata_especial_mandatory_advisory` to `src/aeat/application/calculations/_prorrata_regularizacion.py`: it consumes the pure `is_especial_mandatory` (LIVA art. 103.Dos.2) gate over the ejercicio's general-regime and especial-regime deducción totals and, when especial is obligatory (general exceeds especial by ten percent or more), returns a NON-BLOCKING warning `Notice`; otherwise returns `None` (no noise).
- Carry both compared totals on `Notice.context` (`deduction_under_general`, `deduction_under_especial`) alongside `ejercicio`, `regime = especial`, and the binding `legal_refs = ley-37-1992:art-103` (grounded by W02.P03.S10).
- Import `is_especial_mandatory` from the `aeat.domain.iva` facade and `Notice`/`NoticeSeverity` from `aeat.core.json_contract`; re-export the new builder through the `aeat.application.calculations` package facade `__all__`.
- Add `test_prorrata_especial_mandatory_advisory.py`: fires above the +10% threshold, silent at exactly +10% (strict gate) and below, and fires on a zero especial deduction with a positive general deduction; asserts the WARNING severity and the two totals on `Notice.context`.

## Outcome

The art. 103.Dos.2 mandatory-especial obligation is now surfaced as a non-blocking, structured advisory the operator can act on before filing, never as a refusal of an in-progress filing. Gates green: ruff, ruff format, ty clean on the touched files; 4 new advisory tests plus the existing 13 regularización tests pass; the wider calculations suite is 471 passed with the single failure being the unrelated bienes-inversión `casilla-63` peer broken-HEAD.

## Notes

- Carrier choice: the builder returns a `Notice` directly (rather than the module's usual `CalculationSourceDiagnostic`) precisely to honour the requirement that both totals ride on `Notice.context` — the generic `CalculationSourceDiagnostic` has no free-form context bag and its calculate-path projection carries only `reason`/`source_kind`/`resolver_id`. Building a `Notice` in the application layer is precedented (`application/wizard/_commands.py`). The builder is pure and settlement-time; wiring it onto the live 4T/0A calculate output (which must first compute the especial-regime total) is a downstream integration, matching how the sibling `build_*_advisory` builders are pure functions consumed elsewhere.
- The AEAT-Manual numeric proof of the +10% comparison is S15's oracle; this step's tests assert the gate wiring and non-blocking shape (derived from the LIVA art. 103.Dos.2 ten-percent rule, not from a registry formula).
- Pre-existing peer-owned broken-HEAD: `test_binding_prefill.py::test_modelo_390_prefill...` fails on the bienes-inversión `casilla-63` "missing binding fact" registry-completeness error (documented in tasks #135/#136); unrelated to this step and untouched by it.
