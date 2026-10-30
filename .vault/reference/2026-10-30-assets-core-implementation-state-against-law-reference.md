---
tags:
  - '#reference'
  - '#assets-core'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:0e485c6cf4bdfa6499233c56bc22090d65bcdfda786f6ab08a77ab6964f8afb3'
related:
  - "[[2026-09-21-assets-core-ownership-contracts-reference]]"
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - "[[2026-09-23-assets-core-amortization-method-set-adr]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
---

# `assets-core` reference: `Implementation state of the activity-asset register against the law`

Observed 2026-10-30 on `feature/tui`. Items marked verified were read directly on disk; the others come from read-only discovery reports and need confirming when touched. No tests were run.

## Summary

### What exists

- Domain: `src/cadrumo/domain/renta/actividad_asset/` (`lifecycle.py`, `election.py`, `schedule.py`, `claims.py`). Sixteen methods; forecasts are not stored; claims are immutable and content-hashed.
- Authority: `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`. Coefficient bounds are enforced at `:524`.
- Application and persistence: `src/cadrumo/application/actividad_asset/`, `src/cadrumo/adapters/persistence/profile/actividad_asset.py`, one encrypted history document.
- Tables: `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/parameters/0001-declarations.toml:107,281,455,514`, inherited through 2025. Normal and simplified values match LIS art. 12.1.a and the 1998 Orden. Keys have no territorial dimension and no amortization code reads `tax_residence.ccaa`, which is legally correct.
- Separate registers: `src/cadrumo/domain/bienes_inversion/register.py` for IVA and `src/cadrumo/domain/contribuyente/inventory/` for existencias.
- Operations `ledger.actividad-asset.{create,inspect,correct,forecast,claim,filing-handoff}`, present on CLI, TUI, MCP (generically) and desktop `native/desktop/frontend/src/components/ledger/setup/AssetsPane.tsx`.

### Flow to the forms

A claim reaches Modelo 100 through `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py:100-113` and Modelo 130 casilla 02 through `:87-99` (verified). Register-owned acquisitions are withheld from gasto at `:176-187` (verified). The 5% base in 0222 subtracts 0218, so it is net of amortization as RIRPF art. 30.2.ª requires (verified, `.../revisions/2020/formulas/0001-declarations.toml`).

### Defects against the law

- Casilla 0227 has no Modelo 100 binding, so an intangible claim yields `unrouted_observation`, a member of `GATE_REFUSED_REASONS` (`src/cadrumo/application/modelo/calculation_notes.py:48-50`), refused by `calculation_note_gate.py:47-49`. It blocks check, export and recording rather than misstating the form. Verified. Any taxpayer with a recorded intangible claim cannot complete Modelo 100.
- Modelo 130 counts a claim only once `covered_until` is within the period (`modelo_bindings_actividad_assets.py:88-89`, verified). A full-year claim enters only Q4, nothing prompts quarterly claims, and a missing claim reads as zero. Q1 to Q3 overstate rendimiento unless the operator records intervals by hand.
- Linear charges round per interval (`schedule.py:482-486`, and the non-final constant-percentage branch at `:511-513`, verified), so quarterly claims can differ from the annual figure by cents.
- A ledger row routed to 0208 is deducted as gasto in a year with no claims (`modelo_bindings_actividad_assets.py:204-208`, verified), with no asset behind it. This includes `AMORTIZACION_VIVIENDA_AFECTO`, `HARDWARE_AMORTIZABLE` and `MOBILIARIO_AMORTIZABLE` (`.../facts/2025/mapping/0090-2025-modelo-100-first-slice-expense-routing-mapping.toml:66-68`). `amortizacion_vivienda_afecto` applies a home-area usage ratio to a ledger amount, a second calculation of what the `whole_property` basis computes.
- The low-value ledger route (`src/cadrumo/domain/renta/ledger_expenses.py:616-647`, verified) tests amount only: it does not test the new-asset condition, and it is a second route alongside `LOW_VALUE_FREE`. Its annual cap group at `:1005-1008` covers ledger rows; claims count separately in `claims.py:371-382`, so the two do not share one limit by construction.
- An over-limit purchase outside the register is omitted with only a medium advisory (`ledger_expenses.py:635-640`, verified).
- No disposal: `out_of_service_date` only bounds the window. No minimum-amortization cost reduction, no route to 0179, 0387 or 1846.
- No read model for accumulated amortization, pending basis or remaining value per year. `AssetScheduleHistory` holds the numbers internally.
- `filing_revision_id` and `calculation_revision_id` on `AmortizationClaim` (`claims.py:71-72`) have no producer (verified). `claim_id` hashes every field (`claims.py:110-112`, verified), so they could not be set later without changing identity. Claim ids are not in the drift anchor (`src/cadrumo/application/modelo/_ledger_drift_gate.py:126`), so a later claim can change an already-calculated year's figure without a staleness mark.
- `append_revision` does not recheck recorded claims against a corrected basis (`src/cadrumo/application/actividad_asset/history.py:77-100`, verified).
- `observed_transaction_id` is not checked against the ledger, nor its amount against basis. The basis has no non-deductible IVA component; `basis_amount` is caller-stated (`src/cadrumo/domain/renta/actividad_asset/lifecycle.py`).
- `project_m130` (`claims.py:431-443`) and `activity_asset_expense_observations` (`modelo_bindings_actividad_assets.py:87-99`) each define the same cutoff (verified).
- Estimación objetiva is refused (`src/cadrumo/application/actividad_asset/modality.py:28-31`, verified) and no module amortization table is registered. Casillas 1467 and 1538 stay declared amounts.
- Register fields required by Orden HAC/773/2019 have no complete projection: invoice, supplier and baja are absent or only referenced.
- A foral profile has no amortization-specific refusal in the asset path. `renta_ledger.py:235-266` handles foral residence separately; the reach of that handling is untraced.
- The 2025 incentive citations are not a defect. `rdl-16-2025:art-17` at `.../revisions/2025/revision.toml:10589-10591` sits with the AEAT note, and RDL 7/2026 art. 37 does not reach IRPF 2025 (verified against the amendment footer in `src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md`). No registry file cites RDL 7/2026 yet, so a 2026 edition must author those windows.

### Surfaces

Absent on every surface: asset list (MCP has inspect only), disposal, deducted-to-date view. The TUI declare form is raw JSON (`src/cadrumo/entrypoints/tui/ledger/actividad_asset.py:79`). Naming differs: Activos amortizables, Elementos afectos a la actividad, Depreciable assets, Activity assets. The official terms are inmovilizado, elementos patrimoniales afectos and libro registro de bienes de inversión.

### Vault state

The plans carrying amortization steps S61 to S71 and assets-core S13 are not in the vault, and `export-parity` S06 overlaps the closed `registry-conformance-rectification` P02.S06. Finca amortization has no module; `src/cadrumo/adapters/persistence/profile/__init__.py:11` names one that does not exist.
