---
tags:
  - '#research'
  - '#modelo-inventory'
date: '2026-04-17'
modified: '2026-04-17'
related:
  - '[[2026-04-13-modelo-inventory-research]]'
  - '[[2026-04-13-modelo-inventory-adr]]'
  - '[[2026-04-13-modelo-inventory-plan]]'
  - '[[2026-04-13-modelo-inventory-audit]]'
---

# `modelo-inventory` research: `regulatory-remediation-for-037-130-347-193-and-year-plan-parity`

Follow-up research for issue 108 after manual correctness review against
official AEAT and BOE sources. This pass narrows to the gaps between the
implemented local inventory and the current regulatory position for filing
years 2024, 2025, and 2026.

## Findings

### Scope of this remediation

The prior issue-108 delivery correctly established a typed local registry,
but the review identified five correctness gaps that affect regulatory
accuracy or runtime parity:

- `037` remains represented as an active censal default after its
  suppression from 2025-02-03.
- `130` is over-applied because the implementation does not model the
  professional 70-percent withholding exception.
- `347` is catalogued but not implemented in the filing-history engine.
- `193` is omitted even though it is the annual counterpart to `123`.
- The runtime profile surface cannot distinguish employee-retention and
  professional-retention cases, so `year-plan` cannot faithfully project
  the registry.

### Official-source conclusions

#### 1. Modelo 037 is obsolete for filings submitted from 2025-02-03 onward

AEAT published the ministerial change notice for Orden HAC/1526/2024 and
states that `037` is suppressed, that the order enters into force on
2025-02-03, and that it applies first to `030` and `036` forms filed from
 that date.

Operational conclusion:

- `037` can still exist as historical knowledge for 2024 and early-2025
  historical filing interpretation.
- `037` must not remain the active default censal route for current
  profile applicability or user guidance in 2025-2026.
- `036` becomes the active censal path for the covered use cases from
  2025-02-03 onward.

Affected implementation surfaces:

- `src/aeat/domain/modelos/_codes.py`
- `src/aeat/domain/modelos/_entries/modelo_036.py`
- `src/aeat/domain/modelos/_entries/modelo_037.py`
- `src/aeat/domain/modelos/test_registry.py`
- `src/aeat/domain/modelos/test_codes.py`

#### 2. Modelo 130 remains real, but it is conditional for professionals

AEAT `Modelo 130` instructions and the IRPF regulation both confirm the
same rule:

- `130` is the normal quarterly payment for activities in estimación
  directa.
- Persons carrying out professional activities are not obliged to file in
  relation to those activities if at least 70 percent of the prior-year
  income from that activity was subject to withholding or payment on
  account.

Operational conclusion:

- The review did not prove that `130` is generally wrong.
- The implementation is wrong because it models `130` as always
  applicable in the deadline engine and effectively always applicable in
  the profile projection.
- The runtime profile model needs enough information to distinguish:
  professional activity with the 70-percent exception, and professional
  activity without that exception.

Affected implementation surfaces:

- `src/aeat/domain/deadlines/_models.py`
- `src/aeat/domain/deadlines/_applies.py`
- `src/aeat/domain/deadlines/test_applies.py`
- `src/aeat/domain/deadlines/test_engine.py`
- `src/aeat/domain/modelos/_cli.py`
- `src/aeat/domain/modelos/_entries/modelo_130.py`

#### 3. Modelo 347 is a real threshold-based annual obligation and belongs in year-plan

AEAT states that entrepreneurs and professionals must file `347` when
operations with the same person or entity exceed `3.005,06 EUR` including
VAT in the relevant calendar year, subject to the listed exclusions. AEAT
also places `Año 2025: 347` in the 2026 contributor calendar by
2026-03-02.

Operational conclusion:

- `347` should remain optional in the abstract registry because it is
  threshold-driven.
- It cannot stay absent from the filing-history engine if the project
  claims that informative obligations are implemented.
- The runtime profile model needs a threshold flag for `347`, similar in
  spirit to the current foreign-assets threshold flag used for `720`.

Affected implementation surfaces:

- `src/aeat/domain/deadlines/_models.py`
- `src/aeat/domain/deadlines/_calendar.py`
- `src/aeat/domain/deadlines/_applies.py`
- `src/aeat/domain/deadlines/test_applies.py`
- `src/aeat/domain/deadlines/test_engine.py`
- `src/aeat/domain/modelos/_entries/modelo_347.py`
- `src/aeat/domain/modelos/_cli.py`

#### 4. Modelo 193 must exist if the catalogue claims annualized retenciones are covered

The current registry includes `123` but explicitly documents that `193` is
missing. AEAT still exposes `193` as the annual summary for certain
capital-mobiliario withholdings, and the 2025 calendar shows annual
summary reporting for `193`.

Operational conclusion:

- The current issue-108 claim that annualized retenciones are fully
  catalogued is too broad without `193`.
- `123` should stop carrying a dangling "missing 193" caveat and should
  instead point to a real `193` entry.
- If `123` stays SL-only in v1, `193` should mirror that scope unless the
  research is intentionally widened.

Affected implementation surfaces:

- `src/aeat/domain/modelos/_codes.py`
- `src/aeat/domain/modelos/_entries/modelo_123.py`
- new `src/aeat/domain/modelos/_entries/modelo_193.py`
- `src/aeat/domain/modelos/_registry.py`
- `src/aeat/domain/modelos/test_codes.py`
- `src/aeat/domain/modelos/test_registry.py`

#### 5. Registry and year-plan are not equivalent today

The runtime check `uv run aeat modelos year-plan 2026 --tax-id 12345678Z
--iva-regime GENERAL --has-employees --pays-rent --intracomunitario
--bienes-extranjero --json` emits only:

- `111`
- `115`
- `130`
- `180`
- `190`
- `303`
- `349`
- `390`
- `720`
- `100`

It does not emit `347`, cannot model `193`, and cannot distinguish
professional-retention from employee-retention scenarios because the
runtime profile surface only exposes `has_employees`.

Operational conclusion:

- The project needs an explicit parity invariant between the local modelo
  registry and the deadline/history engine for the subset of modelos that
  claim to be implementable in `year-plan`.
- The user-facing CLI should stop silently implying full profile fidelity
  where the runtime data model is narrower than the registry taxonomy.

### Decision-ready remediation set

This research supports the following corrective implementation decisions:

- Keep `036` and `037` both in the registry, but mark `037` as historical
  / no-longer-current after 2025-02-03 and stop treating it as the default
  current censal route.
- Extend the `ModeloCode` enum to add `193`.
- Add a `modelo_193` metadata entry and wire `123 -> 193`.
- Extend `AutonomoProfile` with explicit booleans for:
  `pays_professionals_with_retencion`,
  `professional_income_withholding_ge_70pct`,
  `third_party_transactions_above_347_threshold`.
- Update the deadline engine so `130`, `111`, `190`, and `347` are driven
  by the richer runtime profile instead of the overloaded `has_employees`
  switch.
- Update the CLI so `year-plan` can represent the professional-retention
  and `347` threshold cases directly.
- Replace the test invariant that "issue 108 equals 20 modelos" with
  behavioural invariants tied to the actual intended coverage.

### Verification target

The remediation is complete only if all of the following become true:

- The registry includes `193`.
- `037` is no longer treated as the active current censal default.
- `year-plan` can emit `347` when the new threshold flag is set.
- `year-plan` can suppress `130` for professional cases meeting the
  70-percent withholding exception.
- The CLI can express the above cases without overloading
  `has_employees`.
- The tests assert these behaviours directly.

## Source Appendix

Primary sources consulted during the remediation review:

- AEAT notice for suppression of `037` and effective date:
  https://sede.agenciatributaria.gob.es/Sede/eu_es/todas-noticias/2025/enero/9/orden-ministerial-modificacion-declaraciones-censales.html
- BOE order `HAC/1526/2024`:
  https://www.boe.es/boe/dias/2025/01/09/pdfs/BOE-A-2025-410.pdf
- BOE `RD 439/2007`, article 110:
  https://www.boe.es/eli/es/rd/2007/03/30/439/con
- AEAT `Modelo 130` instructions:
  https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-130-irpf______esionales-estimacion-directa-fraccionado_/instrucciones.html
- AEAT practical manual, fractional payments:
  https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/manuales-videos-folletos/manuales-practicos/folleto-actividades-economicas/3-impuesto-sobre-renta-personas-fisicas/3_7-pagos-fraccionados.html
- AEAT `Modelo 347` obligation guidance:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/folleto-actividades-economicas/8-declaraciones-informativas/8_2-declaracion-anual-operaciones-terceros-347.html
- AEAT 2026 calendar, `347` by 2026-03-02:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/calendario-contribuyente-2026/calendario-anual/marzo/hasta-2-marzo.html
- AEAT `Modelo 193` page:
  https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI12.shtml
- AEAT 2026 calendar, quarterly `111/115/123/130/303/349`:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/calendario-contribuyente-2026/calendario-anual/abril/hasta-20-abril.html
- AEAT 2026 calendar, annual `720`:
  https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/declaraciones-informativas/modelo-720-decla_____sobre-bienes-derechos-extranjero_/plazos-presentacion.html
- BOE filing windows for `100` exercise 2023:
  https://www.boe.es/eli/es/o/2024/03/18/hac265/dof/spa/pdf
- BOE filing windows for `100` exercise 2024:
  https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-5049
- BOE filing windows for `100` exercise 2025:
  https://www.boe.es/buscar/act.php?id=BOE-A-2026-7041
