---
tags:
  - '#adr'
  - '#iva-autoconsumo-promotor'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-17-modelo-formulas-adr]]"
  - "[[2026-04-27-modelo-390-calc-verify-adr]]"
  - "[[2026-05-21-sii-digital-iva-ledger-adr]]"
  - "[[2026-05-21-corporate-entity-calculation-adr]]"
  - '[[2026-06-04-iva-autoconsumo-promotor-research]]'
---


# `iva-autoconsumo-promotor` adr: IVA autoconsumo promotor Art. 9.1.c LISIVA | (**status:** `accepted`)

## D1 — Context

Ramón (round-24) is a real-estate developer (promotor inmobiliario) operating
as a single-member SL. He converted a property from his construction inventory
to his own rental estate. Under Ley 37/1992 (LISIVA) Art. 9.1.c, this
transfer constitutes an `autoconsumo de bienes` — a deemed self-supply that
triggers IVA on the cost price of the property.

This use case affects an estimated 50,000 real-estate developer SLs and
sole-trader promotors in Spain. Prior to this ADR the M303 calculation engine
had no pathway for autoconsumo; the operator had to manually set the
devengado base. The application emitted no advisory for the scenario.

Art. 79.3 LISIVA grounds the taxable base as the cost price (not market
value) for autoconsumo under Art. 9.1.c. Art. 90 LISIVA sets the general
IVA rate at 21%, which applies to immovable property autoconsumo (residential
construction is taxed at 10% for initial sales but autoconsumo uses the
general rate per Art. 91.Dos.3).

The audit for round-24 classified this gap as a CRITICAL finding: M303
devengado totals were wrong and the operator had no in-application guidance
on the Art. 9.1.c obligation.

## D2 — Decision

### D2.1 — Add `iva.autoconsumo_promotor_base` to the profile schema

Add `iva.autoconsumo_promotor_base: Decimal | None = None` to the
`TaxpayerProfile` IVA sub-schema. This field carries the Art. 79.3 cost
price base provided by the operator. The wizard asks for this value when
`legal_entity_form` is `sl`, `sa`, or `autonomo` and the operator's activity
code suggests real-estate development (IAE group 833 or equivalent CNAE
4110).

### D2.2 — Bind M303 casillas for autoconsumo base and cuota

Add two M303 casillas in the registry:
- `autoconsumo.base` — bound to `iva.autoconsumo_promotor_base` from the
  profile; `input_kind = "binding"`.
- `autoconsumo.cuota` — formula `autoconsumo.base * 0.21` grounded in LISIVA
  Art. 90; `input_kind = "formula"`.

Wire `autoconsumo.cuota` into the `cuota-devengada-total` aggregation formula
so it correctly inflates the total cuota devengada reported in M303 and is
carried through to M390.

### D2.3 — Add legal authority sources in `iva-flow.toml`

Add `art-9` and `art-79` LISIVA legal authority entries to
`src/aeat/_data/registry/aeat/legal/iva-flow.toml` so the binding and
formula declarations can cite them as `legal_refs`.

### D2.4 — CLI injection via `--autoconsumo-promotor-base`

Add `--autoconsumo-promotor-base` flag to `work calculate`. The flag injects
into `binding_values` under the key `iva.autoconsumo_promotor_base`.

## D3 — Alternatives considered

**Alternative A: manual input only.** Leave `autoconsumo.base` as `input_kind
= "manual"`, requiring the operator to supply the value through the general
binding_values path with no named flag. Rejected: the operator cannot
discover the field name without documentation; the advisory cannot be
emitted without a named CLI surface.

**Alternative B: derive base from construction-cost ledger entries.** A future
enhancement could derive the autoconsumo base from property acquisition and
construction cost entries in the transaction ledger. Rejected for this ADR:
the cost-price ledger is not yet implemented. The operator-supplied base is
the appropriate interim approach and is consistent with how AEAT accepts
self-reported autoconsumo bases.

**Alternative C: 10% rate for residential autoconsumo.** The 10% reduced rate
(LISIVA Art. 91.Uno.1.26) applies to the first transfer of residential
property. Autoconsumo under Art. 9.1.c uses the general rate (21%) per the
Dirección General de Tributos binding consultation V2005-15 and subsequent DGT
interpretations. The 10% rate applies to the customer-facing sale, not the
promotor's self-supply. Applying 10% would understate the cuota devengada.

## D4 — Trade-offs

- **Advisory vs enforcement.** The application emits a `DT_AUTOCONSUMO_PROMOTOR`
  advisory WARNING when `legal_entity_form` is compatible with real-estate
  development and `autoconsumo_promotor_base` is absent. The application does
  not refuse to calculate without the field — many SLs in development codes
  have no autoconsumo. The operator must confirm the situation; the application
  cannot determine from activity codes alone whether a specific conversion
  occurred.
- **Art. 9.1.c scope.** This ADR covers only `Art. 9.1.c` (transfer of goods
  from business stock to own assets). Art. 9.1.a (extraction for private use)
  and Art. 9.1.b (transfer for non-business activity) are structurally
  different and deferred to separate plan steps.
- **M390 carry-through.** Wiring `autoconsumo.cuota` into
  `cuota-devengada-total` automatically carries the amount into M390 through
  the existing aggregation chain. No separate M390 casilla is required.

## D5 — Consequences

- M303 gains a bounded `autoconsumo.base` casilla and a computed
  `autoconsumo.cuota` casilla. The `cuota-devengada-total` formula is updated
  to include the new term.
- `TaxpayerProfile` IVA sub-schema gains `autoconsumo_promotor_base`.
- `iva-flow.toml` gains LISIVA Art. 9 and Art. 79 authority entries.
- Oracle test (€1,400,000 base × 21% = €294,000) and anti-tautology ratio
  check pass; all 20 existing M303 registry tests remain green.
- The feature affects approximately 50,000 real-estate developer entities
  in Spain who perform Art. 9.1.c conversions.
