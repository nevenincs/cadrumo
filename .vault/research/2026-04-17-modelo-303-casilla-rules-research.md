---
tags:
  - "#research"
  - "#modelo-303-formulas"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-modelo-formulas-adr]]"
  - "[[2026-04-17-modelo-formula-ruleset-research]]"
  - "[[2026-04-12-modelo-303-390-research]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-13-r1-vat-enumeration-adr]]"
  - "[[2026-04-13-r1-vat-enumeration-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
---

# modelo-303-formulas research (#183)

Date: 2026-04-17
Branch: `feature/183-modelo-303-formulas`
Issue: wgergely/aeat#183
Parent PR: #182 (engine + Modelo 130 wave 1)

## Question

The #183 acceptance is twofold:

1. Codify the Modelo 303 (autoliquidación IVA trimestral) computation
   rules as a period-versioned ruleset on `aeat.domain.formulas`, for
   fiscal years 2024 and 2025.
2. Verify that the downstream **Spanish VAT classification substrate**
   (`aeat.domain.financial.vat`) carries the full taxonomy needed to feed a
   Modelo 303 draft without ad-hoc glue: issuer residence, customer
   residence, customer tax status, transaction kind, period-versioned
   rates and regulations. Close the gaps.

Scope scope-creep: the user instruction expanding #183 explicitly
brings the VAT-substrate completion into this PR because "period-
based filing needs proper rules context in a shifting, non-rigid
environment" and the Modelo 303 ruleset would be disconnected from
the rest of the system if the classification backbone is not solid.

## Scope

### In scope (this PR, "wave 2")

**A. Modelo 303 ruleset on the formula engine (primary #183 ask):**

- IVA devengado — régimen general operaciones interiores (01-09).
- IVA deducible — operaciones interiores corrientes, bienes de
  inversión, importaciones, adquisiciones intracomunitarias,
  rectificaciones, compensación REAGP, regularizaciones (28-45).
- Resultado — 64, 65, 66, 67, 69, 71.
- Two period-versioned rulesets (`modelo_303.2024`, `modelo_303.2025`).

**B. VAT substrate completion (scope-expansion per user request):**

- Period-keyed catalogue (`VAT_CATALOGUES_BY_YEAR[2024|2025]`), with
  `resolve_catalogue(on: date)` helper. Existing 2025 catalogue
  becomes one entry of the year-keyed mapping; the 2024 catalogue
  is added alongside.
- Period-aware `VATRate` resolution already exists via
  `effective_from/until`; this wave **adds the 2024 ES rates and
  the two Ley 7/2024 food-IVA transitional windows** (2024-01-01
  to 2024-06-30 @ 0 %, 2024-07-01 to 2024-09-30 @ 0 %,
  2024-10-01 to 2024-12-31 @ 2 %, 2025-01-01 onwards @ 4 %) and
  the electricity/gas temporary reductions that were in force
  during the 2022-2024 energy crisis.
- **Missing classification axes** (net-new to the VAT substrate):
  - `IssuerResidency` — ES_MAINLAND, ES_CANARIAS, ES_CEUTA_MELILLA,
    EU_MEMBER, THIRD_COUNTRY.
  - `CustomerResidency` — same axis as issuer, scoped to the
    counterparty.
  - `CustomerTaxStatus` — B2B_VAT_REGISTERED (with valid NIF-IVA),
    B2B_NOT_REGISTERED (small business below threshold),
    B2C_CONSUMER, PUBLIC_ADMINISTRATION, UNKNOWN.
  - `TransactionKind` — GOODS, SERVICES_GENERAL,
    SERVICES_DIGITAL_B2C_OSS, SERVICES_LAND_RELATED,
    SERVICES_PASSENGER_TRANSPORT, SERVICES_RESTAURANT,
    IMMOVABLE_PROPERTY, PASSENGER_CAR, CONSTRUCTION_REVERSE_CHARGE,
    WASTE_REVERSE_CHARGE, ELECTRONICS_REVERSE_CHARGE.
- `VATClassificationCriteria` — the pydantic record carrying all
  five classification axes plus the transaction date and
  invoice direction.
- `VATClassification` — pydantic record returned by the resolver:
  `(category, rate_pct, reverse_charge, modelo_303_casilla_mapping)`.
- `classify_vat(criteria: VATClassificationCriteria) -> VATClassification`
  — deterministic lookup backed by a closed ruleset table.
- Modelo 303 casilla bridge: a `Mapping[VATCategory × direction,
  Modelo303Contribution]` that declares which casilla each
  category feeds (e.g., DOMESTIC_GENERAL_21 + ISSUED → base=07,
  cuota=09; DOMESTIC_GENERAL_21 + RECEIVED → cuota=29).

### Explicitly out of scope (deferred)

- **Régimen simplificado** (Modelo 303 casillas 46-63) — REAGP,
  REBU.
- **Recargo de equivalencia** on the liquidación side — the
  VATCategory exists but no Modelo 303 casillas are wired in
  this wave.
- **Canarias IGIC** — separate regime (Modelo 420/421), not
  AEAT Modelo 303. Documented for #??? follow-up.
- **Ceuta/Melilla IPSI** — separate regime.
- **Cross-quarter accumulation of casilla 67** (cuotas a compensar
  de periodos anteriores) — caller-maintained user-input per the
  engine ADR, same pattern as Modelo 130 casillas 05/15.
- **Prorrata definitiva / provisional derivation** (casilla 43) —
  input-only; the engine consumes the user-supplied amount.
- **OSS/MOSS distance-sales threshold auto-determination** — the
  enum slot exists (SERVICES_DIGITAL_B2C_OSS) but the €10,000
  threshold test (Art. 73) is caller-enforced in this wave.
- **Basque / Navarra foral attribution** (casilla 65 < 100) —
  caller-supplied input; no territorial overlay in this wave.
- **Temporary rate ingestion pipeline** — I codify the Ley 7/2024
  food windows inline; a Manual-práctico-IVA PDF ingestion is
  a separate wave (tracked against #???).

## AEAT-primary sources

- **Manual práctico IVA 2025**, AEAT (2025 edition), chapter
  "Modelo 303 — Autoliquidación" — authoritative casilla catalog
  and per-casilla semantics. Manifest under
  `corpus/manuals/iva/2025/` (sha-pinned; fetched 2026-04-12).
- **Manual práctico IVA 2024**, AEAT (2024 edition) — authoritative
  reference for the 2024 casilla catalog and for the Ley 7/2024
  food-IVA transitional windows.
- **Ley 37/1992 de 28 de diciembre, del IVA (LIVA)** — BOE-A-1992-
  28740. Articles used below:
  - `Art. 4` — hecho imponible.
  - `Art. 7` — operaciones no sujetas.
  - `Art. 20` — exenciones interiores.
  - `Art. 21-25` — exportaciones, entregas intracomunitarias,
    exenciones plenas.
  - `Art. 68-70` — reglas de localización (place of supply).
  - `Art. 73-74` — regla especial OSS (distance-sales threshold).
  - `Art. 80` — base imponible y modificaciones.
  - `Art. 84` — sujeto pasivo + inversión del sujeto pasivo.
  - `Art. 89` — rectificación de cuotas.
  - `Art. 90-91` — tipos general, reducido, súper-reducido.
  - `Art. 92-114` — deducciones y regla de prorrata.
  - `Art. 122-134 ter` — régimen simplificado y REAGP.
  - `Art. 148-163` — recargo de equivalencia.
  - `Art. 164` — obligación de autoliquidar.
- **Real Decreto 1624/1992** — Reglamento IVA, artículos 71, 72, 73,
  104-114. BOE-A-1992-28925.
- **Ley 7/2024, de 20 de diciembre** — prolongación de la bajada
  temporal del IVA de alimentos básicos, electricidad y gas
  natural. BOE-A-2024-26683 (retrieval: 2026-04-17).
- **Ley 38/2022, de 27 de diciembre** — bajada temporal del IVA de
  productos energéticos (electricidad 5 %, gas 5 %) aplicable
  durante 2023.
- **Real Decreto-ley 20/2022, de 27 de diciembre** — bajada
  temporal del IVA de alimentos básicos (0 %/ 5 %) para 2023.
- **Orden HAC/819/2024, de 30 de julio** — aprueba el modelo 303
  para ejercicio 2025. BOE núm. 186.
- **Orden HFP/1124/2022, de 18 de noviembre** — modelo 303 para
  ejercicio 2023-2024.
- **Directive 2006/112/EC** — Council VAT Directive. Cited for
  place-of-supply (Art. 44-59 ter), distance sales (Art. 33 +
  59c-bis), exempt export-equivalent intracomunitarias
  (Art. 138), and reverse-charge mechanics (Art. 193-199 bis).
- **European Commission — VAT rates applied in EU Member States**,
  January 2025 issue (already used for the `VAT_RATE_TABLE`).

## Mid-year rule changes

### Régimen general rates (01-09)

| Rate | 2023 | 2024 | 2025 | Legal basis |
| ---- | ---- | ---- | ---- | ----------- |
| General 21 %      | 21 %        | 21 %         | 21 %  | LIVA Art. 90.Uno |
| Reducido 10 %     | 10 %        | 10 %         | 10 %  | LIVA Art. 91.Uno |
| Super-reducido 4 % | 4 %        | 4 %          | 4 %   | LIVA Art. 91.Dos |

Régimen general rates are stable across the 2024-2025 window covered
by this wave.

### Temporary transitional rates (Ley 7/2024 + Ley 38/2022 +
### Real Decreto-ley 20/2022)

These transitional rates do not touch casillas 01-09 directly —
they apply to distinct rate-specific casillas (10, 11, 12 for
the transitional 0 % / 2 % / 5 % tiers). **The Modelo 303
ruleset in this wave does not enumerate casillas 10-12 in the
régimen general casilla set**, but the VAT rate table
(`VAT_RATE_TABLE`) is expanded to carry the transitional windows
so the classification resolver can still tag a transaction with
its correct rate.

**Alimentos básicos (pan común, harinas, leche, quesos, huevos,
frutas, verduras, legumbres, tubérculos, cereales):**

| Window | Rate | Legal basis |
| ------ | ---- | ----------- |
| 2023-01-01 → 2023-06-30 | 0 %  | RDL 20/2022 |
| 2023-07-01 → 2023-12-31 | 0 %  | prorrogado por Ley 31/2022 |
| 2024-01-01 → 2024-06-30 | 0 %  | RDL 20/2023 |
| 2024-07-01 → 2024-09-30 | 0 %  | prorrogado |
| 2024-10-01 → 2024-12-31 | 2 %  | Ley 7/2024 |
| 2025-01-01 onwards       | 4 %  | retorno a súper-reducido (LIVA 91.Dos) |

**Aceite de oliva:**

| Window | Rate | Legal basis |
| ------ | ---- | ----------- |
| 2023-01-01 → 2023-06-30 | 5 %  | RDL 20/2022 |
| 2023-07-01 → 2024-09-30 | 5 %  | prorrogas |
| 2024-10-01 → 2025-12-31 | 4 %  | Ley 7/2024 (reclasificación permanente a 91.Dos) |

**Pastas alimenticias, aceites de semillas:**

| Window | Rate | Legal basis |
| ------ | ---- | ----------- |
| 2023-01-01 → 2024-09-30 | 5 %  | RDL 20/2022 + prorrogas |
| 2024-10-01 → 2024-12-31 | 7.5 %  | Ley 7/2024 |
| 2025-01-01 onwards        | 10 % | retorno a reducido (LIVA 91.Uno) |

**Electricidad (uso doméstico, bajo ciertos umbrales):**

| Window | Rate | Legal basis |
| ------ | ---- | ----------- |
| 2022-07-01 → 2023-12-31 | 5 %  | Ley 38/2022 |
| 2024-01-01 → 2024-06-30 | 10 % | Ley 38/2022 + prorrogas |
| 2024-07-01 onwards        | 21 % | retorno a general |

**Gas natural:**

| Window | Rate | Legal basis |
| ------ | ---- | ----------- |
| 2022-10-01 → 2023-12-31 | 5 %  | Ley 38/2022 |
| 2024-01-01 onwards        | 21 % | retorno a general |

The `aeat.domain.financial.vat._rates` module is expanded to carry these
windows as `VATRate` records with `effective_from` / `effective_until`
set. The test suite asserts `lookup_rate(ES, kind, on=date)` resolves
to the correct rate for every window boundary (± 1 day).

## Modelo 303 — full casilla DAG (wave-2 v1 coverage)

### Operaciones interiores — IVA devengado (régimen general)

| ID  | Label (es) | Kind | Formula |
| --- | ---------- | ---- | ------- |
| 01  | Base imponible al 4 %                        | input    | — |
| 02  | Tipo 4 %                                     | input    | — (constant, defaulted) |
| 03  | Cuota devengada al 4 %                       | computed | `01 × iva.rate_superreducido` |
| 04  | Base imponible al 10 %                       | input    | — |
| 05  | Tipo 10 %                                    | input    | — (constant, defaulted) |
| 06  | Cuota devengada al 10 %                      | computed | `04 × iva.rate_reducido` |
| 07  | Base imponible al 21 %                       | input    | — |
| 08  | Tipo 21 %                                    | input    | — (constant, defaulted) |
| 09  | Cuota devengada al 21 %                      | computed | `07 × iva.rate_general` |

### IVA deducible — bases y cuotas (régimen general)

| ID  | Label (es) | Kind | Role |
| --- | ---------- | ---- | ---- |
| 28-43 | bases + cuotas + rectificaciones + regularizaciones | input | signed / base / cuota |
| 44  | Total a deducir                                          | computed | `29 + 31 + 33 + 35 + 37 + 39 + 40 + 41 + 42 + 43` |
| 45  | Resultado régimen general                                | computed | `(03 + 06 + 09) − 44` |

### Resultado de la liquidación

| ID  | Label (es) | Kind | Formula |
| --- | ---------- | ---- | ------- |
| 64  | Suma de resultados                    | computed | `45` (v1, sin régimen simplificado) |
| 65  | % atribuible al Estado                | input    | default 100 |
| 66  | Atribuible al Estado                  | computed | `64 × 65 ÷ 100` |
| 67  | Cuotas a compensar de periodos anteriores | input    | caller-maintained pool |
| 69  | Resultado                             | computed | `66 − 67` |
| 71  | Resultado de la autoliquidación       | computed | `69` |

**Per-casilla DAG shapes:**

| Casilla | DAG shape |
| ------- | --------- |
| 03      | `ROUND(PERCENT(param("iva.rate_superreducido"), ref("01")))` |
| 06      | `ROUND(PERCENT(param("iva.rate_reducido"), ref("04")))` |
| 09      | `ROUND(PERCENT(param("iva.rate_general"), ref("07")))` |
| 44      | `ROUND(ADD(ref("29"), ref("31"), ref("33"), ref("35"), ref("37"), ref("39"), ref("40"), ref("41"), ref("42"), ref("43")))` |
| 45      | `ROUND(SUB(ADD(ref("03"), ref("06"), ref("09")), ref("44")))` |
| 64      | `ROUND(ref("45"))` |
| 66      | `ROUND(DIV(PERCENT(ref("65"), ref("64")), lit("100")))` |
| 69      | `ROUND(SUB(ref("66"), ref("67")))` |
| 71      | `ROUND(ref("69"))` |

Each computed casilla carries exactly one terminal `RoundFormula`
at 2 dp with `ROUND_HALF_UP`.

## Operator-surface review

The wave-1 operator set (`ADD`, `SUB`, `MUL`, `DIV`, `MIN`, `MAX`,
`CLAMP_POSITIVE`, `PERCENT`, `BRACKETS`, `ROUND`, plus leaf
operands `Literal`, `CasillaRef`, `ParamRef`) is sufficient.

- `RATIO` and `ACCUMULATED_SUM` flagged in #183 are **not required**
  for wave 2 because:
  - Pro-rata percentage derivation is deferred (casilla 43 is
    input-only).
  - Cross-quarter accumulation is caller-maintained (casilla 67 is
    input-only).
- No change to `FormulaOp`.

## VAT classification substrate — gap analysis

### What's already present (keep unchanged)

- `VATCategory` — 16-member closed enum covering domestic/intracomm/
  export/import/recargo/simplificado/erroneous/unknown.
- `EUMemberState` — 27 ISO codes.
- `VATRateKind` — general/reduced/super_reduced/zero/exempt.
- `VATRate` — period-aware rate record with `effective_from/until`.
- `Citation` + `VATRegulation` — trilingual, citation-backed.
- `VAT_CATALOGUE_2025` — 16 regulations, each with ≥2 citations.
- `VAT_RATE_TABLE` — all 27 member states, ES fully expanded.

### What's missing (this PR closes)

| Gap | Fix |
| --- | --- |
| Rate table has only 2025 ES records; 2024 is absent; Ley 7/2024 transitional windows are absent. | Add 2024 ES rates + transitional windows (food, oil, electricity, gas) with correct `effective_from/until`. |
| No period-keyed view over the `VATCatalogue`. The singleton is 2025-only. | Introduce `VAT_CATALOGUES_BY_YEAR: Mapping[int, VATCatalogue]` + `resolve_catalogue(on: date) -> VATCatalogue`. 2024 catalogue is structurally the same set of 16 regulations with 2024 retrieval date and 2024-specific citations (Ley 7/2024 applies a 2 % rate on alimentación during 2024 Q4; the DOMESTIC_SUPER_REDUCED_4 regulation's citation set is augmented accordingly). |
| No issuer-residency axis. | `IssuerResidency` StrEnum. |
| No customer-residency axis. | `CustomerResidency` StrEnum. |
| No customer-tax-status axis. | `CustomerTaxStatus` StrEnum. |
| No transaction-kind axis. | `TransactionKind` StrEnum covering goods/services/digital/immovable/reverse-charge variants. |
| No deterministic `(axes) → VATCategory` resolver. | `classify_vat(VATClassificationCriteria) -> VATClassification`. |
| No bridge from `VATCategory` to Modelo 303 casillas. | `MODELO_303_CASILLA_MAPPING: Mapping[(VATCategory, InvoiceKind), Modelo303Contribution]`. |

### Classification axes — full set

```python
class IssuerResidency(StrEnum):
    ES_MAINLAND = "es_mainland"         # Territorio aplicación IVA (TAI)
    ES_CANARIAS = "es_canarias"         # IGIC territory, out of LIVA
    ES_CEUTA_MELILLA = "es_ceuta_melilla"  # IPSI territory
    EU_MEMBER = "eu_member"             # any of the 27 EU member states
    THIRD_COUNTRY = "third_country"     # non-EU

class CustomerResidency(StrEnum):
    ES_MAINLAND = "es_mainland"
    ES_CANARIAS = "es_canarias"
    ES_CEUTA_MELILLA = "es_ceuta_melilla"
    EU_MEMBER = "eu_member"
    THIRD_COUNTRY = "third_country"

class CustomerTaxStatus(StrEnum):
    B2B_VAT_REGISTERED = "b2b_vat_registered"       # Has valid NIF-IVA
    B2B_NOT_REGISTERED = "b2b_not_registered"       # Small business below threshold
    B2C_CONSUMER = "b2c_consumer"                   # Private individual
    PUBLIC_ADMINISTRATION = "public_administration" # AAPP client
    UNKNOWN = "unknown"                              # Sentinel

class TransactionKind(StrEnum):
    GOODS = "goods"
    SERVICES_GENERAL = "services_general"
    SERVICES_DIGITAL_B2C_OSS = "services_digital_b2c_oss"   # Art. 70.Uno.4º
    SERVICES_LAND_RELATED = "services_land_related"         # Art. 70.Uno.1º
    SERVICES_PASSENGER_TRANSPORT = "services_passenger_transport"  # 10 %
    SERVICES_RESTAURANT = "services_restaurant"             # 10 %
    IMMOVABLE_PROPERTY = "immovable_property"               # Art. 20.Uno.22º
    PASSENGER_CAR = "passenger_car"
    CONSTRUCTION_REVERSE_CHARGE = "construction_reverse_charge"  # Art. 84.Uno.2º.f
    WASTE_REVERSE_CHARGE = "waste_reverse_charge"             # Art. 84.Uno.2º.c
    ELECTRONICS_REVERSE_CHARGE = "electronics_reverse_charge"  # Art. 84.Uno.2º.g
```

### Classification resolution table (closed, deterministic)

The `classify_vat` function implements a closed decision table. The
rule is: the FIRST matching row determines the classification.
Rules are ordered from most-specific to most-generic. A sentinel
`UNKNOWN` is returned when no row matches.

| Rule | issuer | customer | cust. tax status | kind | outgoing | incoming | category |
| ---- | ------ | -------- | ----------------- | ---- | -------- | -------- | -------- |
| R01  | ES | ES | any B2*/AAPP | CONSTRUCTION_REVERSE_CHARGE | ✔ | ✔ | domestic_reverse_charge (Art. 84.Uno.2º) — NEW CATEGORY GROUP ① |
| R02  | ES | ES | any B2*/AAPP | WASTE_REVERSE_CHARGE | ✔ | ✔ | domestic_reverse_charge ① |
| R03  | ES | ES | any B2*/AAPP | ELECTRONICS_REVERSE_CHARGE | ✔ | ✔ | domestic_reverse_charge ① |
| R04  | ES | ES | B2C_CONSUMER \| PUBLIC_ADMIN | IMMOVABLE_PROPERTY | ✔ | ✔ | DOMESTIC_EXEMPT (Art. 20.Uno.22º) |
| R05  | ES | ES | any | any non-RC | ✔ | ✔ | DOMESTIC_* (at applicable rate; resolved by `TransactionKind` → `VATRateKind`) |
| R10  | ES | EU_MEMBER | B2B_VAT_REGISTERED | GOODS | ✔ | — | INTRA_COMMUNITY_SUPPLY (Art. 25) |
| R11  | ES | EU_MEMBER | B2B_VAT_REGISTERED | GOODS | — | ✔ | INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE (Art. 13) |
| R12  | ES | EU_MEMBER | B2B_VAT_REGISTERED | SERVICES_GENERAL | ✔ | — | DOMESTIC_NOT_SUBJECT (Art. 69.Uno, reverse charge at dest.) |
| R13  | ES | EU_MEMBER | B2B_VAT_REGISTERED | SERVICES_GENERAL | — | ✔ | INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE (Art. 84.Uno.2º.a) |
| R14  | ES | EU_MEMBER | B2C_CONSUMER | SERVICES_DIGITAL_B2C_OSS | ✔ | — | DOMESTIC_NOT_SUBJECT (OSS at destination, Art. 70.Uno.4º) |
| R15  | ES | EU_MEMBER | B2C_CONSUMER | GOODS | ✔ | — | distance_sales (above threshold → OSS; below → DOMESTIC_*). Threshold caller-enforced; classification returns DOMESTIC_NOT_SUBJECT + note. |
| R20  | ES | THIRD_COUNTRY | any | GOODS | ✔ | — | EXPORT_THIRD_COUNTRY_ZERO_RATED (Art. 21) |
| R21  | ES | THIRD_COUNTRY | any | GOODS | — | ✔ | IMPORT_THIRD_COUNTRY (Art. 18) |
| R22  | ES | THIRD_COUNTRY | any | SERVICES_GENERAL | ✔ | — | DOMESTIC_NOT_SUBJECT (Art. 69.Uno place-of-supply) |
| R30  | ES_CANARIAS/CEUTA_MELILLA | * | * | * | * | * | DOMESTIC_NOT_SUBJECT (out of TAI) |
| R99  | * | * | * | * | * | * | UNKNOWN (fall-through) |

**NEW CATEGORY GROUP ①:** the existing enum uses
`INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE` for inversión del
sujeto pasivo. Domestic reverse-charge (Art. 84.Uno.2º) is NOT
intracomunitario. To avoid mislabeling, this PR adds one new
`VATCategory` member: **`DOMESTIC_REVERSE_CHARGE`**. Rationale:
it's a structurally different regulation (issuer residence = ES,
customer residence = ES, but the sujeto pasivo reverses) and
deserves its own regulation entry with its own citations.

### Modelo 303 casilla mapping (bridge table)

The `MODELO_303_CASILLA_MAPPING` is keyed by
`(VATCategory, InvoiceKind)` and returns a tuple of casilla
contributions. A contribution records:

- `casilla_id`
- `role` — `BASE` or `CUOTA`
- `sign` — `+1` or `-1` (for rectifications)
- `rate_kind` — `None` for non-rate-specific, or the `VATRateKind`
  (the rate is resolved separately via `lookup_rate`).

| Category | Direction | Casillas |
| -------- | --------- | -------- |
| DOMESTIC_GENERAL_21 | ISSUED | 07 (base, +1), 09 (cuota, computed from 07×0.21) |
| DOMESTIC_REDUCED_10 | ISSUED | 04 (base, +1), 06 (cuota, computed from 04×0.10) |
| DOMESTIC_SUPER_REDUCED_4 | ISSUED | 01 (base, +1), 03 (cuota, computed from 01×0.04) |
| DOMESTIC_ZERO | ISSUED | 01 base, cuota 03 is 0 (computed) |
| DOMESTIC_EXEMPT | ISSUED | — (informational, declared on 390 casillas) |
| DOMESTIC_NOT_SUBJECT | ISSUED | — |
| DOMESTIC_GENERAL_21 | RECEIVED | 28 (base, +1), 29 (cuota, +1) |
| DOMESTIC_REDUCED_10 | RECEIVED | 28 (base, +1), 29 (cuota, +1) |
| DOMESTIC_SUPER_REDUCED_4 | RECEIVED | 28 (base, +1), 29 (cuota, +1) |
| DOMESTIC_REVERSE_CHARGE | ISSUED | 07 or 04 or 01 (base depending on rate), no cuota |
| DOMESTIC_REVERSE_CHARGE | RECEIVED | 28 (base, +1), 29 (cuota, +1) (self-assessed) |
| INTRA_COMMUNITY_SUPPLY | ISSUED | 59 (base, +1) informational only in v1 |
| INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE | RECEIVED | 36 (base, +1), 37 (cuota, +1) — both devengada + deducible with same cuota (self-assessed) |
| EXPORT_THIRD_COUNTRY_ZERO_RATED | ISSUED | 60 (base, +1) informational in v1 |
| IMPORT_THIRD_COUNTRY | RECEIVED | 32 (base, +1), 33 (cuota, +1) |
| RECARGO_EQUIVALENCIA | — | Out of scope v1 |
| REGIMEN_SIMPLIFICADO | — | Out of scope v1 |
| OPERACION_NO_SUJETA | — | — |
| ERRONEOUS_INVOICE | — | — (excluded until rectified) |
| UNKNOWN | — | — (quarantined for human review) |

Casillas 59 (entregas intracomunitarias base), 60 (exportaciones
base) are informational-only in régimen general liquidación (they
feed into 390 annual summary). They are included in the bridge
table but the Modelo 303 wave-2 ruleset does NOT declare them
(scope boundary — next wave adds them alongside the régimen
simplificado casillas).

## Cross-references to existing artifacts

- `src/aeat/domain/financial/vat/_schema.py` — existing enum + record
  types. The new enums and classification records live in a new
  module `_classification.py` that re-uses the existing
  `_StrictFrozen` / `_StrictMutable` base and the existing
  `VATCategory` + `EUMemberState` enums. The addition of
  `DOMESTIC_REVERSE_CHARGE` is a single enum line and a matching
  `VATRegulation` record in the catalogue.
- `src/aeat/domain/financial/vat/_rates.py` — the 2024 ES rate set and
  the Ley 7/2024 / Ley 38/2022 transitional windows are added
  here as additional `VATRate` entries on the ES row.
- `src/aeat/domain/financial/vat/_catalogue.py` — factored into a
  per-year catalogue builder. 2024 catalogue re-uses 2025
  regulation records unchanged (structurally stable) + ships
  one additional citation on `DOMESTIC_SUPER_REDUCED_4` quoting
  Ley 7/2024 (for reviewer trace).
- `src/aeat/domain/financial/vat/_modelo_303_mapping.py` — NEW module
  exposing `MODELO_303_CASILLA_MAPPING` as the bridge between
  classification and ruleset.
- `src/aeat/domain/formulas/_rulesets/modelo_303_2024.py` and
  `_2025.py` — NEW ruleset modules.
- `src/aeat/domain/formulas/_rulesets/__init__.py` — register new
  rulesets.
- Tests colocated under each module (Rust-style).

## Integration consistency check

The Modelo 303 ruleset's `iva.rate_*` parameters mirror the
`VATRate` values for ES from the substrate. A dedicated test
(`test_modelo_303_ruleset_rate_consistency`) asserts that the
ruleset's parameter for `iva.rate_general` equals
`lookup_rate(ES, GENERAL, on=ruleset.effective_from).pct / 100`.
This catches rate drift between the two substrates at test time.

## Non-functional considerations

- **Relative-imports mandate** (#162) — every new internal import
  inside `src/aeat/` uses relative syntax.
- **Public-API discipline** — new classification types are re-
  exported from `aeat.domain.financial.vat.__init__` so downstream callers
  never reach `_classification.py` directly.
- **Pydantic v2 strict+frozen** on every record.
- **Trilingual contract** — the new category labels are
  `Translatable` with `es` authoritative.
- **Decimal discipline** — all rate percentages stored and
  compared as `Decimal`; floats rejected.
- **Logging** — every new module uses
  `aeat.core.logging.get_logger(__name__)`.
- **Testing** — `@pytest.mark.unit` tests colocated; every
  classification rule has at least two cases (match + boundary
  miss).

## Deliverables

1. `src/aeat/domain/formulas/_rulesets/modelo_303_2024.py`
2. `src/aeat/domain/formulas/_rulesets/modelo_303_2025.py`
3. Updated `src/aeat/domain/formulas/_rulesets/__init__.py` registry.
4. `src/aeat/domain/financial/vat/_classification.py` — new enums,
   criteria record, classification record, `classify_vat()` resolver.
5. `src/aeat/domain/financial/vat/_modelo_303_mapping.py` — bridge table.
6. Extended `src/aeat/domain/financial/vat/_rates.py` — 2024 ES rates,
   Ley 7/2024 + Ley 38/2022 transitional windows.
7. Extended `src/aeat/domain/financial/vat/_catalogue.py` — per-year
   builder, `VAT_CATALOGUES_BY_YEAR`, `resolve_catalogue(on)`.
8. Extended `src/aeat/domain/financial/vat/_schema.py` — one new
   `VATCategory.DOMESTIC_REVERSE_CHARGE` enum member.
9. Extended `src/aeat/domain/financial/vat/__init__.py` — public
   re-exports.
10. Colocated unit tests:
    - `test_modelo_303_2024.py` — formula values for ≥10
      scenarios per AEAT worked example.
    - `test_modelo_303_2025.py` — same shape.
    - `test_modelo_303_ruleset.py` — structural (period ambiguity,
      rate-consistency with VATRate, registry binding).
    - `test_classification.py` — every rule in the table + two
      boundary cases each.
    - `test_modelo_303_mapping.py` — every VATCategory has a
      declared mapping (or is explicitly marked out-of-scope).
    - `test_rates_temporal.py` — Ley 7/2024 boundary tests
      (± 1 day on each transition).
    - Existing `test_catalogue.py` extended with 2024 catalogue
      round-trip.

All deliverables ship in a single PR.
