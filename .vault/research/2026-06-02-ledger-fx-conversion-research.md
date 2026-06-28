---
tags:
  - '#research'
  - '#ledger-fx-conversion'
date: '2026-06-02'
modified: '2026-06-02'
related: []
---



# `ledger-fx-conversion` research: `foreign-currency conversion: legal basis, accounting practice, and a stable free per-date rate source`

The ledger carries foreign-currency rows (GBP/USD via Revolut). To project them
into the modelos a `value_in_eur` must be computed at a legally-correct exchange
rate, from a data source that is stable, free, per-date, and auditable in
production. This research grounds (a) which rate Spanish tax law and accounting
require, and (b) which concrete data source production should consume. It feeds
the sibling ADR `ECB euro reference rates as the canonical FX source` and unblocks
the persona-surfaced HIGH defect that the CLI import path never converts foreign
rows.

## Findings

### F1 — The "official exchange rate" in Spanish law IS the ECB euro rate

`Ley 46/1998, de 17 de diciembre, sobre introducción del euro`, art. 36
establishes that the official exchange rate of the national currency against other
currencies is **the one the European Central Bank publishes for the euro**. Every
downstream tax rule that says "tipo de cambio oficial" therefore resolves to the
ECB euro reference rate. This is the single anchor that unifies IRPF, IVA, and the
accounting rules below onto one source.

### F2 — IRPF: ECB official rate at the date of the operation

`LIRPF` art. 14.2.e) (imputación temporal) together with `Ley 46/1998` art. 36:
amounts collected or paid in foreign currency are imputed at their euro value at
the **ECB official rate on the date of the operation** (devengo). DGT criteria
(e.g. consulta V2422-20) confirm conversion at the ECB official rate on the
operation date; for ganancias/pérdidas the rate in force on the date of the
patrimonial alteration. So renta income (export client receipts) and deductible
expenses in foreign currency convert at the ECB rate at the row's value/operation
date — exactly the corpus's Revolut rows.

### F3 — IVA: art. 79.Once, "tipo vendedor del Banco de España" at devengo

`Ley 37/1992 (LIVA)` art. 79.Once: when the consideration is fixed in a currency
other than the euro, the taxable base converts using "el tipo de cambio vendedor,
fijado por el Banco de España, que esté vigente en el momento del devengo." The
literal text names a Banco de España **selling** rate, not the ECB **reference**
(mid) rate. Reconciliation: since euro adoption the Banco de España no longer
fixes an independent daily selling rate for the major currencies — it relays the
**ECB euro reference rates** as the official rates (per `Ley 46/1998` art. 36).
In practice AEAT's own worked examples and practitioners convert with the ECB
reference rate at devengo. The residual nuance (a historical "vendedor"/selling
spread vs the ECB mid rate) is immaterial for the ECB reference rate that BdE now
publishes; it is documented as a known approximation, not a silent choice.

### F4 — Accounting (PGC NRV 11ª): spot rate at the transaction date

The Plan General de Contabilidad, Norma de Registro y Valoración 11ª (moneda
extranjera): every foreign-currency transaction is converted to euro at the
**tipo de cambio de contado** (spot rate) on the **transaction date** — the
immediate-delivery rate between the two currencies. The ECB daily reference rate
is the standard spot proxy used for this purpose. This aligns the bookkeeping
basis with the tax basis on the same source and date convention.

### F5 — Data source: ECB euro foreign exchange reference rates (eurofxref)

The ECB publishes the euro foreign exchange reference rates every **TARGET
working day at ~16:00 CET**, free, with no API key and no rate limit, in XML:
- daily: `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`
- last 90 days: `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml`
- full history since 1999: `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml`

Format: nested `Cube` elements, one per date, each holding `currency`/`rate`
pairs. **Quote direction: EUR-base** — a rate is `1 EUR = rate CCY`. So
`value_in_eur = amount_ccy / rate(EUR->CCY)` (NOT a multiply). The corpus
manifest's `fx_rates_to_eur` are the inverse convenience form (1 CCY = X EUR);
production must consume the ECB EUR-base quote and invert.

### F6 — Coverage gaps and the date-fallback convention

The ECB publishes only on TARGET working days: **no rate on weekends/holidays**.
For an operation on a non-publication date the established convention (and the
ECB's own guidance) is to use the rate of the operation date when present, else
the **most recent prior published working-day rate**. This must be an explicit,
tested rule, not an implicit nearest-match.

### F7 — Licensing / suitability

ECB reference rates are published for information; the ECB notes they are intended
as reference (indicative) rates rather than transaction rates. For tax conversion
they are nonetheless THE legally-official source via `Ley 46/1998` art. 36 and are
what AEAT examples use. They are free to reuse with attribution; bundling a
point-in-time snapshot of `eurofxref-hist.xml` in the repo gives deterministic,
offline, reproducible per-date lookup without a runtime network dependency.

## Recommendation (feeds the ADR)

Adopt the **ECB euro foreign exchange reference rates** as the canonical FX
source. Acquire them by **bundling a versioned snapshot of `eurofxref-hist.xml`**
in the data tree (deterministic, offline, auditable, refreshed on release), read
EUR-base and invert to get `value_in_eur = amount_ccy / rate`, apply the rate at
the operation/value date with most-recent-prior-working-day fallback, and record
the rate + source + rate-date as provenance on the transaction. This satisfies
IRPF (F2), IVA (F3), and PGC (F4) from one grounded source and unblocks the
import-normalizer wiring.

## Sources

- BOE — Ley 37/1992 del IVA (art. 79): https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740
- AEAT sede — cálculo de la base imponible (contraprestación en divisas): https://sede.agenciatributaria.gob.es/Sede/iva/calculo-iva-repercutido-clientes/calculo-base-imponible.html
- DGT consulta V2422-20 (tipo de cambio IRPF): https://petete.tributos.hacienda.gob.es/consultas/?num_consulta=V2422-20
- Iberley — tipo de cambio moneda extranjera a efectos de IRPF: https://www.iberley.es/practicos/caso-practico-tipo-cambio-moneda-extranjera-efectos-irpf-91778
- PGC NRV 11ª moneda extranjera: https://www.plangeneralcontable.com/?tit=normas-de-registro-y-valoracion-contable&name=GeTia&contentId=man_nvaloracion&manPage=22
- ECB euro reference rates (full history XML): https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml
- ECB euro reference rates (daily XML): https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml
