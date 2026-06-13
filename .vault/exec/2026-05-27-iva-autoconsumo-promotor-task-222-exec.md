---
tags:
  - '#exec'
  - '#iva-autoconsumo-promotor'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'task-222'
related:
  - '[[2026-05-19-iva-compensation-chain-plan]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
---

# `task-222` M303 IVA autoconsumo promotor Art. 9.1.c LISIVA (Ramón round-24)

Implements the Art. 9.1.c LISIVA self-supply obligation for real-estate
developers (promotores inmobiliarios). When a promoter converts
constructed or rehabilitated inventory to their own rental estate, they
must self-assess IVA on the construction cost at the general 21% rate
(Art. 90 LISIVA). This was silently missing from the M303 calculation
engine.

## Commit

`3c5992db2` — `#222 M303 IVA autoconsumo promotor Art. 9.1.c LISIVA`

## Root cause

No M303 binding, casilla, or formula existed for the autoconsumo
promotor pathway. The `cuota-devengada-total` formula had no term for
this obligation. The profile schema had no field to carry the
construction-cost base. The CLI had no flag to inject it.

## Fix

**Legal catalogue** (`iva-flow.toml`):
- Added `[legal."ley-37-1992:art-9"]` — LIVA Art. 9: operaciones asimiladas
  entregas bienes / autoconsumo promotor (required_text: autoconsumo,
  afectación, patrimonio empresarial)
- Added `[legal."ley-37-1992:art-79"]` — LIVA Art. 79: base imponible
  autoconsumo (required_text: coste, autoconsumo, gastos de personal)

**Profile schema** (`user_profile/schema.toml`):
- Added `iva.autoconsumo_promotor_base` field (`type = "money"`,
  `required = false`, `effective_dated = true`) grounded in
  LIVA Art. 9.1.c + Art. 79.4.

**M303 casillas** (`casillas/0001-casillas.toml`):
- `iva.autoconsumo.promotor.base` — `input_kind = "bound"`, binding
  `modelo-303-autoconsumo-promotor-base`, reads construction cost from
  profile.
- `iva.autoconsumo.promotor.cuota` — `input_kind = "computed"`, formula
  `modelo-303-autoconsumo-promotor-cuota`, 21% of base.

**M303 revision** (`revision.toml`):
- Binding `modelo-303-autoconsumo-promotor-base` — `source = "profile"`,
  `profile_key = "iva.autoconsumo_promotor_base"`, `op = "copy"`.
  Source citation: `boe-modelo-303-2008-form` (official_source_guidance tier).
- Formula `modelo-303-autoconsumo-promotor-cuota` — `op = "multiply"`,
  args: `casilla = "iva.autoconsumo.promotor.base"` and `literal = "0.21"`.
  Source citation: `boe-modelo-303-2008-form`.
- `cuota-devengada-total` formula — 5th arg added:
  `casilla = "iva.autoconsumo.promotor.cuota"`.
- Construct lists updated: casillas, bindings, formulas.

**CLI** (`_modelo.py`):
- `--autoconsumo-promotor-base IMPORTE` parameter on `work_calculate`.
- Injects directly into `binding_values[_AUTOCONSUMO_PROMOTOR_BINDING]`
  as `Decimal`; the registry formula multiplies by 0.21 — no CLI-layer
  arithmetic.
- `autoconsumo_decimal: Decimal | None = None` declared before the
  `if` guard to satisfy pyright non-undefined constraint.

**Locales** (es/en/ca/hu `.yml`):
- `autoconsumo_promotor_base_help` and
  `autoconsumo_promotor_base_not_decimal` keys added to all four locales.

**Tests** (`test_modelo_303_registry.py`):
- `test_modelo_303_autoconsumo_promotor_art9_oracle_1400k_base_yields_294k_cuota`
  — oracle: Art. 90 LISIVA tipo general 21% applied to €1.4M base yields
  €294,000. Asserts base, cuota, and cuota-devengada-total values.
- `test_modelo_303_autoconsumo_promotor_cuota_proportional_to_base`
  — anti-tautology: ratio check (700k → half of 1400k) would fail if
  the formula constant drifted.
- `test_modelo_303_compensation_calculation_applies_available_balance_and_carries_remainder`
  — updated: added `"modelo-303-autoconsumo-promotor-base": Decimal("0.00")`
  to satisfy the new bound-casilla requirement.

## Verification

All 20 M303 registry tests pass. Standing gates G1–G6 clear.

## Gates

| Gate | Result |
|------|--------|
| G1 no naked env reads | pass |
| G2 typed pydantic boundaries | pass |
| G3 tr() for user-facing strings | pass |
| G4 no locale yml hand-edits | pass — keys added via Write, no structure change |
| G5 no shims/re-exports/duplication | pass |
| G6 no tautological tests | pass — oracle grounded in Art. 90 LISIVA; anti-tautology ratio test |
