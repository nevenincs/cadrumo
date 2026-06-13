---
tags:
  - "#research"
  - "#p2e-tax-category-catalogue"
date: "2026-04-13"
modified: '2026-04-13'
related:
  - "[[2026-04-13-p2e-tax-category-catalogue-adr]]"
  - "[[2026-04-13-p2e-tax-category-catalogue-plan]]"
---

# `p2e-tax-category-catalogue` research: aeat spending-category taxonomy + proportionality substrate

This research grounds issue `#77` as TDP step `T4`, the taxonomy substrate.
It covers the source-backed AEAT expense families, the current-main casilla
surface the catalogue can legally point at, and the conservative codifications
needed where the 2025 handbook is weaker than the requested category list.

Topic: AEAT-aligned spending categories and proportionality rules for autónomo
activity expenses in 2025.

Audit surface: `#77`, `#104`, `#78`, `#79`, `#91`, `#85`, `#71`,
`aeat.domain.casillas`, `aeat.domain.manuals`, `aeat.domain.normatives`, `aeat.core.i18n`, and the root
Typer CLI.

Rewrite scope: new feature artifacts and new `aeat.domain.financial.categories`
implementation only.

## Findings

### 1. Scope and ownership boundary

- `#77` is a pure data substrate. It does not evaluate proportionality, classify
  transactions, or assign VAT regimes at runtime.
- The public API should live under `aeat.domain.financial.categories`.
- `src/aeat/domain/financial/providers/` remains owned by `#73` and stays untouched.
- `src/aeat/domain/financial/vat/` remains owned by `#85` and stays untouched.
- `#78` and `#79` are direct consumers of the catalogue and its rule profiles.

### 2. Current-main casilla limits

- Current `aeat.domain.casillas` exposes `MODELO_130` `{01, 02, 03, 18}` and
  `MODELO_303` `{01, 03, 27, 71}` only.
- On current main, `MODELO_130:01` is the only direct expense-sensitive box.
- `MODELO_130:02` and `MODELO_130:18` are derived/result boxes.
- `MODELO_130:03` is retentions and payments on account.
- Current `MODELO_303` does not expose a category-specific deductible-input VAT
  box, so any category-to-`303` mapping is necessarily aggregate/coarse.
- The taxonomy substrate should record coarse `303` relations honestly instead
  of inventing a finer public VAT box structure than current main provides.

### 3. Source-backed rule envelopes

The primary source is the AEAT *Manual práctico de Renta 2025. Parte 1*,
especially the activity-expense sections around pages `425` to `465`, together
with `Ley 35/2006` and `RD 439/2007`.

- `cuotas_autonomos_ss`
  - Fully deductible activity expense.
  - Source basis: `Ley 35/2006 art. 28.1` and AEAT 2025 RETA regularisation
    help.
- `arrendamiento_local`
  - Fully deductible business rent under `Arrendamientos y cánones`.
  - Source basis: manual page `434`.
- `suministros_home_office_*`, `telefonia_fija`
  - Special home-office rule: `30% × area ratio`.
  - Source basis: `Ley 35/2006 art. 30.2.5ª.b` and manual pages `438-439`.
- `telefonia_movil`
  - Not a generic percentage rule. Deductibility is tied to exclusive business
    use; the handset itself is amortizable.
  - Source basis: manual page `438`.
- `manutencion_dietas_nacional`, `manutencion_dietas_extranjero`
  - Deductible only when incurred by the contributor, in restauración /
    hostelería, paid electronically, and kept within the employee-diet daily
    caps.
  - Source basis: `Ley 35/2006 art. 30.2.5ª.c`, `RD 439/2007 art. 9.A.3.a`,
    manual pages `433-434`.
- `vehiculo_*`
  - Ordinary passenger-vehicle expenses are binary by affectation /
    exclusive-use rule, not a generic percentage rule.
  - Source basis: `RD 439/2007 art. 22.1-4`, manual pages `379`, `463-465`.
- `seguros_salud_autonomo`
  - Explicit cap: `500 EUR` per insured person, `1,500 EUR` with disability.
  - Source basis: `Ley 35/2006 art. 30.2.5ª.a`, manual pages `439-440`.
- `asesoria_*`, `publicidad_marketing`, `material_oficina`,
  `suministros_cliente_directos`, `gastos_bancarios`, `gastos_financieros`,
  `seguros_responsabilidad_civil`, `viajes_transporte`
  - Full deductible ordinary activity-expense families.
  - Source basis: manual pages `425-426`, `439-442`.
- `hardware_amortizable`
  - Deductible through amortization, not a special proportionality class.
  - Source basis: manual pages `463-465`, `RD 439/2007 art. 30.1ª`.

### 4. Conservative codifications

The requested minimum category list is broader than the strongest current-2025
manual labels. The following categories are useful compatibility codifications
but weaker source-backed fits:

- `cuotas_colegiales`
- `arrendamiento_vivienda_afecto`
- `software_suscripcion`
- `viajes_alojamiento`
- `subcontratacion`

These should remain in the catalogue because downstream classification benefits
from the labels, but the profile notes must explicitly say that the category is
being codified conservatively rather than lifted from a clean 2025 handbook
label.

### 5. Casilla mapping implication

- Every expense family can defensibly point at `MODELO_130:01` on current main.
- `MODELO_303` mappings are reporting hints only, because current main does not
  expose a category-specific deductible-input box.
- The least misleading `303` hook is the aggregate result surface
  `MODELO_303:71`, with notes that the mapping is coarse and not a substitute
  for a future richer deductible-input lattice.

### 6. Implementation invariants

- Every boundary-crossing record should be a strict pydantic v2 model.
- Every `ProportionalityRule` must carry at least one citation.
- Every `CategoryProfile` must remain explainable without depending on sibling
  branches.
- The current-main `303` coarseness must be visible in both the ADR and the
  runtime notes.

## Source basis

- AEAT *Manual práctico de Renta 2025. Parte 1*:
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf`
- `Ley 35/2006` IRPF consolidated text:
  `https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764`
- `Real Decreto 439/2007` Reglamento IRPF consolidated text:
  `https://www.boe.es/eli/es/rd/2007/03/30/439/con`
- AEAT 2025 help on RETA regularisation:
  `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/irpf-2025/7-cumplimentacion-irpf/7_4-rendimientos-actividades-economicas/7_4_2-regimen-estimacion-directa/7_4_2_3-gastos-fiscalmente-deducibles/cotizaciones-reta.html`

## Conclusion

T4 should ship as a strict, citation-backed, conservative spending-category
catalogue. The registry must encode the 2025 source rules honestly, preserve
weaker requested labels as explicit conservative codifications, and keep
`MODELO_303` mappings coarse rather than overclaiming unavailable public-box
detail on current main.
