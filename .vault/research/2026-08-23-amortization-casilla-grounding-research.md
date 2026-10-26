---
tags:
  - '#research'
  - '#amortization-casilla-grounding'
date: '2026-08-23'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:0203f7100d7fa3fee8830f598d1507dd0c3b251be649c674c7b5169502a052ca'
related: []
---

# `amortization-casilla-grounding` research: `Modelo 100 amortization authorities`

The 2025 form has two direct-estimation activity destinations—0208 for material fixed assets and 0227 for intangible fixed assets—while rental-property amortization belongs to the separate capital-inmobiliario envelope at 0131. The encrypted asset and amortization ledgers are not yet authoritative filing sources: recorded amounts are not derived or validated against the applicable method, coefficient, useful-life window, accumulated basis cap, service dates, special elections, or material/intangible destination. Box 0208 is also already claimed by the transaction-ledger expense source, so a new asset source must replace that category's authority or fail on collision; it cannot silently sum both.

## Findings

### The official activity destinations distinguish material and intangible assets

Orden HAC/277/2026's 2025 Modelo 100 form assigns “Dotaciones del ejercicio para amortización de inmovilizado material” to 0208 and the intangible equivalent to 0227, within each direct-estimation activity. Evidence: https://www.boe.es/eli/es/o/2026/03/25/hac277/dof/spa/pdf, page 27; the former source file and `c0227.toml:1` in that revision.

The application `AssetClass` vocabulary includes both tangible classes and software, but has no explicit legal material/intangible axis. `AmortizacionEntry` contains only `asset_id`, `year`, and a non-negative amount. Evidence: the former source file and `:191-224`. It cannot safely select 0208 versus 0227 from the persisted amortization entry alone.

### A recorded amount is not proof of fiscal deductibility

For simplified direct estimation, the AEAT publishes a linear table with distinct maximum coefficients and periods by class; for example buildings are 3 percent/68 years, machinery 12 percent/18 years, transport 16 percent/14 years, and information equipment and software 26 percent/10 years. Normal direct estimation follows the LIS amortization rules, and used assets, special elections, accelerated amortization, and excess deductions add different constraints. Evidence: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/fase-1-determinacion-rendimiento-neto/amortizaciones-dotaciones-ejercicio-fiscalmente-deducibles/especialidades-fiscales-amortizaciones-modalidad-simplificada.html and https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/fase-1-determinacion-rendimiento-neto/amortizaciones-dotaciones-ejercicio-fiscalmente-deducibles/reglas-amortizacion.html.

`AssetRecord` stores cost basis, acquisition date, optional useful life, allocation ratio, and a free-text special election, but no calculation service joins those facts to annual legal coefficients. `AmortizacionLedger` does not reject duplicate `(asset_id, year)` entries, verify the asset exists, enforce accumulated deductions within basis, prorate by in-service days, or prove that the recorded amount follows the selected regime. Evidence: the former source file; `rg -n "AssetClass|AmortizacionEntry" src/cadrumo/application src/cadrumo/domain` finds no production calculator. The evidence therefore disfavors treating the current scalar ledger as filing authority without a governed computation and validation contract.

### Existing transaction-ledger authority already reaches 0208

Revision 2025 binds 0208 to `ledger_renta_gastos_estimacion_directa_aggregation`. Its canonical routing maps affected-home amortization, amortizable hardware, and amortizable furniture transaction categories to 0208. Evidence: the former source file and `src/cadrumo/domain/renta/_first_slice_routing.py:209-221`.

Those transaction rows are derived-expense declarations, not asset-schedule proof. The asset ledger and transaction ledger therefore describe the same filing fact through competing evidence paths. Three alternatives remain: retain transaction authority and classify the asset ledger as duplicate; make the validated asset schedule authoritative and exclude amortization transaction categories; or define precedence. Summing is unsafe double counting, and silent precedence obscures ownership. The evidence favors a validated asset schedule as the eventual authority, with explicit rejection or exclusion of transaction amortization rows, but the ADR must decide this replacement.

### Finca amortization is a distinct source contract

Rental-property amortization is governed in the capital-inmobiliario envelope and lands at 0131, not activity boxes 0208/0227. The finca calculation uses construction-only basis, rental days, a three-percent annual rate, and an accumulated acquisition-cost cap. Evidence: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c04-rendimientos-capital-inmobiliario/gastos-deducibles/cantidades-destinadas-amortizacion.html; the former source file; the former source file.

The finca ledger is per property/year and depends on rental-contract facts. Reusing the activity-asset selector would conflate legal regime, destination, basis, temporal grain, and ownership. It should remain a distinct fincas source contract and be delivered with the broader finca aggregate slice.

### Only the 2025 destination window is directly grounded here

This research directly verifies the 2025 annual form and manual. Earlier repeated registry roles are not by themselves official continuity evidence. The first asset-amortization connection should be revision 2025 only unless annual authorities for earlier revisions are separately verified.

This research did not design the legal coefficient registry, adjudicate every freedom/acceleration election, or decide whether unsupported historic entries should be recomputed or remain manual.

## Sources

- https://www.boe.es/eli/es/o/2026/03/25/hac277/dof/spa/pdf
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/fase-1-determinacion-rendimiento-neto/amortizaciones-dotaciones-ejercicio-fiscalmente-deducibles/especialidades-fiscales-amortizaciones-modalidad-simplificada.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c07-rendimientos-actividades-economicas-estimacion-directa/fase-1-determinacion-rendimiento-neto/amortizaciones-dotaciones-ejercicio-fiscalmente-deducibles/reglas-amortizacion.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c04-rendimientos-capital-inmobiliario/gastos-deducibles/cantidades-destinadas-amortizacion.html

- `src/cadrumo/domain/renta/_first_slice_routing.py:209-221`
