---
tags:
  - '#audit'
  - '#registry-grounding-spotcheck'
date: '2026-07-03'
modified: '2026-07-03'
related: []
---

# `registry-grounding-spotcheck` audit: `recent-tax-year change cross-reference spot check`

## Scope

A grounding spot-check: web-search the concrete recent (2023-2026) AEAT tax
changes for the surfaces the export-hardening campaign touched, then cross-
reference each against the registry revisions to surface drift or gaps. This is a
sampling pass, not an exhaustive audit -- each finding is a candidate for a fuller
per-modelo grounding review. External sources: BOE Orden HAC/1347/2024 (2025
módulos, BOE-A-2024-24949), Orden HFP/1172/2022 (2023 módulos, BOE-A-2022-20025),
and the 2023-2025 temporary-IVA-rate consejo-de-ministros / BOE record.

## Findings

### eo-general-reduction-2025-grounded | low | Modelo 100/2025 estimación-objetiva general reduction is correct

The 2025 estimación-objetiva general reduction is grounded correctly: parameter
`renta-2025-estimacion-objetiva-reduccion-general-rate` carries `value = 5`
(percent), `legal_refs = ["orden-hac-1347-2024:art-4", "ley-35-2006:art-31"]`, and a
`source_citation` `required_text = ["estimación objetiva", "reducción general"]`.
This matches the external record (Orden HAC/1347/2024 sets the 2025 general
reduction at 5%). Confirmed OK.

### eo-general-reduction-2023-2024-missing | medium | the estimación-objetiva general reduction is absent for Modelo 100/2023 and 100/2024

The general reduction is a year-specific BOE figure: 10% for 2023 (Orden
HFP/1172/2022), 5% for 2024, 5% for 2025. Only the 2025 revision carries a
`estimacion-objetiva-reduccion-general-rate` parameter; the 2023 and 2024 revisions
have no equivalent parameter and no inline `0.90`/`0.95` reduction factor in their
estimación-objetiva formulas (both years DO model EO -- 24 EO/módulos files each --
so the absence is a gap, not an out-of-scope surface). A 2023/2024 EO filer's
rendimiento would therefore omit the general reduction (10% / 5%), over-declaring
income. NUANCE to resolve before fixing: the 2025 parameter itself does not appear
to be referenced by any formula (no consumer found for
`renta-2025-estimacion-objetiva-reduccion-general-rate`), so either the reduction is
applied through a binding/construct the grep did not surface, or modelo 100 receives
an already-reduced rendimiento from the módulos worksheet. The fix, once the
application mechanism is confirmed, is to backfill the 2023 (10%, Orden
HFP/1172/2022 art. 4) and 2024 (5%) parameters grounded against the bundled corpus,
and to confirm the 2025 parameter is actually consumed.

### eo-gasoleo-fertilizantes-minoracion | low | the 2023-2024 gasóleo-agrícola/fertilizantes minoración should be absent for 2025 (confirm)

The external record notes the minoración del rendimiento neto por adquisición de
gasóleo agrícola y fertilizantes existed for 2023-2024 and was removed for 2025. No
explicit `gasoleo`/`fertilizante` minoración parameter was found in the 131/303
módulos registries for any year, so this is either modelled under a different name
or not modelled. Worth a targeted check that (a) if the 2023/2024 minoración is
modelled it is present for those years, and (b) it is NOT carried into 2025/2026.

### iva-303-modulos-coefficients-year-naming | medium | the M303 régimen-simplificado módulos coefficients are named -2025 but applied across 2023-2026

The `2023-y-siguientes` M303 revision carries the módulos parameters
`m303-modulos-iva-coeficientes-2025` / `-cuota-minima-pct-2025`, and that single
revision serves filing years 2023-2026. AEAT publishes the régimen-simplificado
coefficients per annual módulos orden, so applying the 2025 set to 2024 and 2026 is
likely a grounding drift. Bounded impact: these feed the `internal_only` advisory
casillas `modulos-iva-cuota-devengada`/`derivada` that are excluded from every
export (see the fichero-boe-parity-gate audit), so the filed `.boe`/workbook is
unaffected -- but the módulos advisory figure itself is only correct for 2025.

### iva-temporary-food-energy-rates | low | the 2023-2024 temporary IVA rates are not a Modelo 303 calc gap

The 2023-2024 temporary reductions (basic foods 0% then 2%, olive oil 0%, seed oils
5%) and their return to normal in 2025 (foods 4%, olive oil 4%, seed oils 7.5%) are
product-classification changes, not new rate values. The IVA rate catalogue
(`aeat/iva/rates.toml`) carries the standard rate values (21/10/4/0) referenced to
Ley 37/1992, and Modelo 303 aggregates the taxpayer's actual per-invoice cuotas from
the ledger rather than deriving product rates, so the temporary rates do not require
a 303 calc change. No gap on the 303 filing surface; the rate catalogue could carry
the temporary product windows for advisory completeness but that is not filing-grade.

## Recommendations

- Confirm how the estimación-objetiva general reduction is applied in Modelo 100
  (formula vs binding/construct vs pre-reduced input). If it is a registry
  parameter the calc consumes, backfill the 2023 (10%) and 2024 (5%) parameters
  grounded against the bundled corpus, and verify the 2025 parameter is consumed.
- Split or re-ground the M303 régimen-simplificado módulos coefficients per filing
  year (2023/2024/2025/2026) rather than a single -2025 set, or explicitly document
  that the advisory is 2025-only. Low urgency: the figures are excluded from every
  export.
- Targeted check of the gasóleo-agrícola/fertilizantes minoración: present for
  2023-2024, absent for 2025-2026.
- Treat this as a sampling pass; a fuller per-modelo grounding review of the
  2023-2026 revisions against each year's BOE orden is the follow-up.
