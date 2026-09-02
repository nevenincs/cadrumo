# Ledger corpus — calculation-grounded operator-testimonial fixture

This corpus is the **single source of truth** every AEAT ledger CLI operator
persona and every operator-journey test works against. It is a hand-authored,
500+ row, cross-year (2025 full year → 2026 H1) ledger for one coherent
fictional taxpayer, delivered as **raw bank exports** (exactly what an import
looks like — no tax facts on the wire) plus a typed **ground-truth manifest**
(`ground-truth.manifest.json`) that is the verification oracle.

The ledger is the backbone that feeds the modelo calculation engines, so every
row is authored to project cleanly through the three aggregation pipelines:

| Pipeline | Module | Feeds |
| --- | --- | --- |
| IVA ledger | `application/aggregation/iva_ledger.py` | M303 / M390 |
| Renta expenses | `application/aggregation/_renta_ledger.py` | M100 |
| Renta income | `application/aggregation/_renta_income_ledger.py` | M130 |

Projection axes (authored on every row, recorded in the manifest):
`direction` × (`iva_category` / `iva_rate`) × (`business_classification` /
`business_pct`) × `category_id` × `counterparty_country` ×
(`fx_rate` / `value_in_eur`) × period window.

## Taxpayer backstory

**Ana Ríos Velasco** — NIF `12345678Z` — autónoma, residente fiscal en España
(`source_jurisdiction = "ES"`).

- **Actividad económica** (estimación directa simplificada, IVA régimen general):
  desarrollo de software y consultoría IT. Clients domestic (ES) and foreign
  (DE intracom, UK/US third-country export). `irpf_category =
  actividades_economicas_directa_simplificada`.
- **Rendimientos del trabajo**: part-time employed lecturer — monthly nómina
  with IRPF retención. `irpf_category = trabajo` (must be **rejected** from M130).
- **Capital inmobiliario**: lets one flat — monthly rent received.
  `irpf_category = capital_inmobiliario`.
- **Capital mobiliario (ahorro)**: quarterly bank savings interest.
  `irpf_category = capital_mobiliario_ahorro`.
- Personal/private life: groceries, restaurants, gym, holidays — `PERSONAL`,
  non-deductible, ignorable noise that personas must filter out.

## Accounts (4 raw source files)

| id | file | provider layout | currency | role |
| --- | --- | --- | --- | --- |
| `bbva-business-eur` | `bbva-business-eur.csv` | BBVA | EUR | primary business current account |
| `caixabank-personal` | `caixabank-personal.csv` | CaixaBank | EUR | personal + mixed (salary, rent, phone) |
| `revolut-multi` | `revolut-multi.csv` | Revolut | GBP/USD/EUR | foreign client receipts, foreign SaaS, travel |
| `n26-savings` | `n26-savings.csv` | N26 | EUR | savings, interest income, secondary |

Approx distribution (≥500 total): BBVA ~180, CaixaBank ~140, Revolut ~110,
N26 ~70. Spread across 18 months (2025-01 → 2026-06).

### Exact raw layouts (authored to parse on first import)

- **BBVA** — `;` delimited, comma decimal, `DD/MM/YYYY`:
  `Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda;Referencia`
- **CaixaBank** — `;` delimited, comma decimal, `DD/MM/YYYY`:
  `Fecha movimiento;Fecha valor;Concepto;Importe;Divisa;Saldo;Referencia operación`
- **Revolut** — `,` delimited, dot decimal, `YYYY-MM-DD HH:MM:SS`:
  `Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance`
- **N26** — `,` delimited, dot decimal, `YYYY-MM-DD`:
  `Date,Value date,Payee,Payment reference,Amount (EUR),Currency,Transaction type`

`Referencia` columns make transaction identity operator-visible and the oracle
join stable. Revolut/N26 keep realistic layouts; their rows join by natural key
`(file, completed/booked date, amount, description)` which is unique per file.
`Saldo`/`Balance` running balances are authored consistently per account so a
persona can sanity-check continuity.

## Taxonomy coverage matrix (every member exercised ≥ once)

**TransactionDirection**: INCOMING (client income, salary, rent, interest),
OUTGOING (all expenses), INTERNAL_TRANSFER (paired BBVA↔CaixaBank / Revolut
top-ups — same amount, opposite sign, both accounts, never tax-relevant).

**BusinessClassification**: BUSINESS (pure business expense/income), PERSONAL
(groceries/holidays), MIXED + `business_pct` (home-office utilities 0.30,
mobile 0.50, vehicle fuel 0.40). NOT_YET_PROCESSED / PROCESSED_UNCLASSIFIED /
SKIPPED_BY_RULE are produced by the *pipeline* during persona runs, not authored
into income/expense rows.

**IvaCategory** — all 16 placed on concrete rows:
| category | worked example row |
| --- | --- |
| `domestic_general` | ES client invoice; office supplies, software |
| `domestic_reduced` | hotel/restaurant business travel |
| `domestic_super_reduced` | books / professional press |
| `domestic_zero` | (rare) qualifying zero-rated domestic |
| `domestic_exempt` | RC seguro responsabilidad civil, formación (art. 20) |
| `domestic_not_subject` | indemnización / non-taxable receipt |
| `domestic_reverse_charge` | inversión sujeto pasivo (e.g. móviles/portátiles >threshold, obra) |
| `intra_community_supply` | services to DE business client (+ EU state DE) |
| `intra_community_acquisition_reverse_charge` | SaaS from IE vendor (+ EU state IE) |
| `intra_community_triangulation` | one triangular goods op (+ EU state) |
| `export_third_country_zero_rated` | services to US/UK client (no EU state) |
| `import_third_country` | hardware import from US vendor |
| `recargo_equivalencia` | one supplier line carrying RE surcharge |
| `regimen_simplificado` | one módulos-regime line (edge) |
| `operacion_no_subjeta` → `operacion_no_sujeta` | non-subject operation |
| `unknown` / `erroneous_invoice` | a malformed/rectified row (gated, not declarable) |

**SpendingCategory** — all 41, spread by family: social_security
(`cuotas_autonomos_ss`, `mutualidad_alternativa`, `cuotas_colegiales`),
premises (`arrendamiento_local`, `ibi_local_afecto`,
`arrendamiento_vivienda_afecto`…), home_office_suministros (luz/agua/gas/internet
as MIXED 0.30), home_office_ownership, telecoms (`telefonia_movil` MIXED 0.50,
`telefonia_fija`), office (`material_oficina`, `software_suscripcion`,
`hardware_amortizable`, `mobiliario_amortizable`, `reparaciones_conservacion`),
vehicle (combustible/mantenimiento/seguro/peaje/parking as MIXED 0.40), meals
(`manutencion_dietas_nacional`/`extranjero`), professional_services
(`asesoria_fiscal`/`juridica`/`contable`), travel
(`viajes_transporte`/`alojamiento`), insurance
(`seguros_responsabilidad_civil`, `seguros_salud_autonomo`), financial
(`gastos_bancarios`, `gastos_financieros`), direct_costs
(`suministros_cliente_directos`, `subcontratacion`), taxes
(`tributos_fiscalmente_deducibles`).

**IRPF category** (RentaIncomeType): `actividades_economicas_directa_simplificada`
(business income), `trabajo` (salary — rejected from M130),
`capital_inmobiliario` (rent), `capital_mobiliario_ahorro` (interest).

**Lifecycle scenarios** (driven during persona/journey runs, seeded by the
corpus): rows tagged in the manifest as `scenario` candidates for
archive/stash/split/merge — e.g. one large mixed invoice to **split** into
business+personal children; a duplicate re-export to test **likely_duplicate**;
a misfiled row to **stash**; a personal row mistakenly business to **archive**.

**Multicurrency**: Revolut GBP/USD income + USD SaaS expense + an FX exchange.
The manifest records the ECB `fx_rate` and `value_in_eur` expected at each
row's value date; the corpus-fidelity test wires `CurrencyNormalizationService`
with those rates so the rows normalize rather than gating as
`UNSUPPORTED_CURRENCY`.

**Cross-period**: invoices raised in one quarter, paid the next (e.g.
`F-2025-018` raised 2025-03, paid 2025-04) so devengo-vs-caja and the M130
cumulative window are exercised. At least one invoice straddles the year
boundary (raised 2025-12, paid 2026-01).

## Ground-truth manifest schema (`ground-truth.manifest.json`)

```jsonc
{
  "taxpayer": { "name": "...", "nif": "12345678Z", "regime": "estimacion_directa_simplificada" },
  "accounts": [ { "id": "bbva-business-eur", "provider": "BBVA", "currency": "EUR", "file": "bbva-business-eur.csv" } ],
  "fx_rates": [ { "currency": "GBP", "date": "2025-02-14", "rate_to_eur": "1.1980" } ],
  "transactions": [
    {
      "account": "bbva-business-eur",
      "ref": "BBVA-2025-0007",
      "booked_date": "2025-02-14",
      "amount": "1234.56",          // signed, matches CSV exactly
      "currency": "EUR",
      "description": "...",          // matches CSV exactly (natural-key join)
      "expected": {
        "direction": "INCOMING",
        "business_classification": "BUSINESS",
        "business_pct": null,
        "category_id": null,
        "iva_category": "domestic_general",
        "iva_rate": "0.21",
        "taxable_base": "1020.30",
        "iva_amount": "214.26",
        "irpf_category": "actividades_economicas_directa_simplificada",
        "counterparty_country": null,
        "source_jurisdiction": "ES",
        "fx_rate": null,
        "value_in_eur": null,
        "projects_to": { "modelo_303": "repercutido_base_general", "modelo_130": "ingresos", "modelo_100": "ingresos_explotacion" }
      },
      "scenario": null               // or "split" | "stash" | "archive" | "likely_duplicate" | "merge"
    }
  ],
  "expected_aggregates": {
    "2025": {
      "modelo_303": { "1T": { "repercutido_base_general": "...", "soportado_base_general": "...", "...": "..." } },
      "modelo_130": { "1T": { "ingresos_acumulados": "...", "gastos_acumulados": "..." } }
    }
  }
}
```

### Oracle discipline (anti-tautology)

Per `aeat-quality-gates` and `aeat-quality-gates`, the oracle
asserts **structural projection** (this row → this casilla/modelo bucket) and
**arithmetic base/cuota sums** (summation of authored bases) — it does **not**
re-compute registry tax formulas. `taxable_base` + `iva_amount` are authored
from the invoice face (base × statutory rate), the same way an operator reads a
real invoice; the registry-formula cuota outputs (e.g. M130 pago fraccionado %)
are validated elsewhere against AEAT worked examples, not invented here.

## Files

- `bbva-business-eur.csv` · `caixabank-personal.csv` · `revolut-multi.csv` ·
  `n26-savings.csv` — raw bank exports.
- `ground-truth.manifest.json` — the oracle.
- `classify/*.csv` — derived bulk `classify --file` inputs (ref→facts),
  used by operator-journey tests after id resolution.
