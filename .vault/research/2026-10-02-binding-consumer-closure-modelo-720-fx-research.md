---
tags:
  - '#research'
  - '#binding-consumer-closure'
date: '2026-10-02'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:a548e0f7eb367d3cf5771f5b911f186542b79d7501b3915235b25c4e2484c636'
related: []
---

# `binding-consumer-closure` research: `Modelo 720 legally binding exchange rate`

Question: which exchange rate, and at which date, turns a foreign-currency Modelo 720
valuation into the euro amount the record design requires, and where the existing FX port
diverges from that rule. It matters because S06 composes the type 2 record from source
observations in native currency, and a wrong rate date or a silent zero is a
filing-grade error. Conclusion: the binding rate is the ECB euro reference rate (Ley 46/1998
art. 36); the date is fixed by DGT doctrine per class and situation; six cases stay
advisory; the port needs a rate-date input and two correctness fixes. Raw official captures
were taken on 2026-10-02 (scratch evidence set, not bundled).

## Findings

### No Modelo 720 provision fixes a rate
RD 1065/2007 arts. 42 bis, 42 ter and 54 bis and Orden HAP/72/2013 (as amended by Orden
HFP/1180/2023) require amounts "en euros o su contravalor" (type 2 pos. 432-446 and 447-461)
and carry no currency field and no rate rule. Evidence: BOE-A-2007-15984, BOE-A-2013-954,
BOE-A-2023-22221.

### The binding source is the ECB reference rate
Ley 46/1998 art. 36 defines the "cambio oficial" as the rate the ECB publishes for the euro,
directly or through the Banco de España, which republishes the identical figures daily in
the BOE. Series `EXR/D.{CCY}.EUR.SP00.A`, published on TARGET days. Evidence:
BOE-A-1998-29216; BdE resolutions BOE-A-2026-19690, BOE-A-2025-167, BOE-A-2026-243,
BOE-A-2022-24664.

### Rate date per class and situation (DGT consultas vinculantes)
- Accounts: the 31 December balance and the Q4 average balance are both converted at the
  31 December rate (V0691-13); the Q4 average is computed in the original currency first and
  then converted, and a multi-currency account is one record (V1133-22).
- Securities, IIC, insurance and real-estate rights valued at 31 December: the 31 December
  ECB rate of the declared year (V0555-18, V1096-18, V3973-15, V0751-25, V1051-26).
- Real estate valued at acquisition: the 31 December rate of the declared year, not the
  acquisition-date rate (AEAT FAQ; V2669-17); that euro value is then frozen and later FX
  movements do not count toward the 20.000 EUR increase (V2669-17).
- Extinction or transfer during the year: the rate at the extinction date, stated for
  accounts (AEAT FAQ) and for transferred real estate (V1051-26, V2045-23); for securities,
  IIC and insurance only by analogy.
- The 50.000 EUR and 20.000 EUR tests run on converted euro values; FX movements count for
  every block except real estate (AEAT FAQ). The comparison base is "la última declaración"
  (arts. 42 bis.5, 42 ter.5, 54 bis.7), not necessarily the previous year.
- Non-publication day: 31 December is not a TARGET closing day; on a weekend the last rate
  is the preceding Friday's. The "último tipo de cambio oficial publicado con anterioridad"
  wording exists only in Patrimonio doctrine (V1049-19; AEAT Manual Patrimonio 2025) and
  reaches the 720 by analogy (V1133-22).
- Currencies the ECB does not publish (ARS, CUP, VES, CLP, COP, RUB since 2022): the DGT still
  says "ECB at 31 December" (V1096-18, V0737-21, V0614-25, V1051-26), which cannot be applied
  literally; only Patrimonio doctrine offers a market value of the currency unit. BdE Table
  1.3 is monthly and informational, not official.
- Comparables: Patrimonio (modelo 714) converts at the devengo-date ECB rate; pre-1999
  euro-area currencies use the irrevocable Reglamento (CE) 2866/98 rates; IRPF converts gains
  at the alteration date (V1554-23). 720 doctrine cross-refers only to Patrimonio and Ley
  46/1998 art. 36.

### Cases the sources leave unsettled (advisory)
1. Weekend or holiday fallback for an extinction date.
2. Currencies with no ECB rate.
3. Rate for listed shares valued at a Q4 average price (V1059-13 left unanswered).
4. Acquisition-value rate in a real-estate extinction record.
5. Securities, IIC and insurance extinguished during the year (analogy only).
6. A real-estate asset first declared in a later year.

### Gaps against the existing FX port
- G1: no 720 path converts currency (`src/cadrumo/application/aggregation/foreign_assets.py:130`
  takes `valuation_eur`; valuation bindings are `manual_input`).
- G2: `Modelo720RowObservation.currency_code` defaults to EUR
  (`src/cadrumo/domain/calculations/registry/detail_record_bindings.py:104`), filled at
  `src/cadrumo/application/calculations/row_set_assembly.py:772`; non-EUR is accepted silently.
- G3: `resolve_fx_conversion_stamp` uses the record's operation date
  (`src/cadrumo/domain/currency/service.py:120-123,150`); the 720 needs the legally fixed date.
- G4 (matches): the ECB provider falls back to the latest observation within 14 days
  (`src/cadrumo/adapters/outbound/fx/ecb_provider.py:52-55,115-131`).
- G5: the stamp and `NormalizedAmount` record the requested date, not the ECB observation
  date actually used (`src/cadrumo/domain/currency/service.py:102,153`).
- G6 (matches): series, inversion precision and half-up cent rounding
  (`src/cadrumo/adapters/outbound/fx/ecb_provider.py:134-140`, `src/cadrumo/core/money/rounding.py:43`).
- G7 (refuses correctly): a discontinued currency yields `MISSING_RATE`.
- G8: the live ECB answers 404 for an unknown code, mapped to `ExchangeRateProviderError`
  (`src/cadrumo/adapters/outbound/fx/ecb_provider.py:224-231`), while the former test stub answered an empty 200.
- G9: no real-estate euro freeze in
  `src/cadrumo/application/calculations/foreign_asset_redeclaration.py:200-203,234-249`.
- G10: the 20.000 EUR baseline is the previous filing year (720 bindings 330-357), not "la
  última declaración"; no dual 31 December / Q4 test for accounts.
- G11: `MISSING_RATE` sets `eur_amount = 0.0` (`src/cadrumo/domain/currency/service.py:76-88`);
  `src/cadrumo/application/calculations/row_set_assembly.py:784` defaults a missing valuation
  to `Decimal("0")`.

The evidence favours: the ECB rate through the existing port with a caller-supplied legal
rate date; refusal for every non-converted status; the six cases above advisory. The
row-carrier ADR amendment must settle the rule.

## Sources
- https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984 (RD 1065/2007)
- https://www.boe.es/buscar/act.php?id=BOE-A-2013-954 (Orden HAP/72/2013)
- https://www.boe.es/buscar/doc.php?id=BOE-A-2023-22221 (Orden HFP/1180/2023)
- https://www.boe.es/buscar/act.php?id=BOE-A-1998-29216 (Ley 46/1998)
- https://www.boe.es/buscar/act.php?id=BOE-A-1991-14392 (Ley 19/1991, Patrimonio)
- https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764 (Ley 35/2006)
- https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186 (Ley 58/2003)
- Banco de España resolutions BOE-A-2026-19690, BOE-A-2025-167, BOE-A-2026-243, BOE-A-2022-24664
- https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/declaraciones-informativas/modelo-720-decla_____sobre-bienes-derechos-extranjero_/preguntas-frecuentes/valoracion.html
- AEAT Manual práctico Patrimonio 2025
- https://petete.tributos.hacienda.gob.es/consultas/ (DGT V0691-13, V1059-13, V3973-15,
  V2669-17, V0555-18, V1096-18, V1049-19, V2615-20, V0737-21, V1133-22, V2045-23, V1554-23,
  V0614-25, V0751-25, V1051-26)
- https://data.ecb.europa.eu/ (EXR reference rates; TARGET closing days)
