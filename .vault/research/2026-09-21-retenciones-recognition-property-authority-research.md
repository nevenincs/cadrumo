---
tags:
  - '#research'
  - '#retenciones'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:ba8d78947340a57237a63634ad95d9525bcada69935bfeeabb3cb30d5e0fa561'
related:
  - '[[2026-09-21-retenciones-workflow-observation-payment-contract-adr]]'
  - '[[2026-06-24-retenciones-perceptor-count-adr]]'
---

# `retenciones` research: recognition and property authority

The accepted observation contract treats payment as the universal recognition event,
but that is too broad for capital income and too weak for Modelo 180 property detail.
For the 2025 filing frame, official authority supports three timing families and a
narrow two-year Modelo 193 reporting sequence for amounts left uncollected. The Modelo
180 design expressly counts emitted type-2 records and permits a no-cadastral-reference
alternative under situation code 4.

## Findings

### Recognition is authority-selected, not caller-selected

RIRPF article 78 makes payment/satisfaction the general trigger and routes capital and
investment-fund cases to articles 94 and 98. Article 94.1 recognizes ordinary movable-
capital income on exigibility or earlier payment/delivery; article 94.2 recognizes
financial-asset transmission, amortization, or reimbursement at the transaction and
requires withholding at formalization; article 98 uses formalization for IIC events.
`src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:1314-1319`,
`:1673-1678`, `:1786-1788`.

RIS article 65 applies an earlier-of-exigibility/payment rule to supported IS income and
formalization rules to financial assets and IIC operations. This does not establish
IRNR permanent-establishment timing. `src/cadrumo/_data/corpus/normatives/html/rd-634-2015.html.extracted.md:1021-1026`.

The provisions support typed evidence for paid/satisfied, exigibility-or-earlier-
payment, and formalization. They do not support caller rule selection or a caller-
supplied recognition date. Formalization branches must not automatically materialize to
123/193 because some operations belong to other modelo families. Unknown residence,
IRNR, and ungrounded income/regime/modelo combinations must refuse.

### Modelo 193 has a narrow pending-payment and later-payment sequence

For keys A, B, and D, the 2025 design marks an amount accrued in the year but unpaid
because the holder did not present for collection with `PENDIENTE`. The accrual-year
record uses prescribed pending-recipient values and retains the financial amounts.
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/01-193-orden-eha-3377-2011-actualizado-por-orden-hac-1430-2025-de-3-de-diciembre-357-kb-pdf.pdf.extracted.md:851-899`.

When the holder later collects, actual recipient information is reported in the
payment-year return and `EJERCICIO DEVENGO` identifies the earlier year. The field is
forbidden outside that case. `.../modelo_193/files/01-193-orden-eha-3377-2011-actualizado-por-orden-hac-1430-2025-de-3-de-diciembre-357-kb-pdf.pdf.extracted.md:900-935`.

A supported worked case is IRPF interest, key B/nature 03, contractually maturing on 15
December 2025, where the holder does not present for collection and payment occurs on
20 January 2026. Article 94 recognizes the liability on 15 December: Modelo 123 includes
it in 4T 2025. Modelo 193 for 2025 emits the pending row. Modelo 193 for 2026 emits the
actual recipient with `EJERCICIO DEVENGO=2025`. The settlement is a second required
annual disclosure phase, not a second economic allocation or periodic liability. It
does not automatically correct 2025; an amendment is needed only if that filing was
omitted or wrong. Other nonpayment causes and keys remain unsupported.

### Modelo 180 counts records and permits conditional property identities

The `2023-y-siguientes` design defines `NÚMERO TOTAL DE PERCEPTORES` as the number of
type-2 records and counts the same recipient every time it appears.
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.extracted.md:110-114`.

One row carries recipient, modality, accrual year, and one property block. Situation
codes 1-3 describe a property with a cadastral reference; code 4 expressly permits one
without it. Code 4 therefore needs an explicit stable local property key while the
official cadastral field stays empty. Different accrual years require separate records.
`.../modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.extracted.md:203-275`, `:306-310`, `:370-439`;
`src/cadrumo/locales/es/modelo/schema/180.yml:16-67`.

For supported positive rows the authority-compatible grouping dimensions are filing
year, recipient NIF, modality, accrual year, and property identity. Property identity is
situation plus cadastral reference and exported address for situations 1-3, or situation
plus exported address for situation 4. Reimbursements add sign. Amounts spanning
properties need explicit attribution; the evidence does not support guessed splits.

### Boundaries not established

IRNR permanent-establishment timing, generic unpaid M193 cases outside A/B/D non-
collection, and M180 treatment for an unpaid IS landlord remain unsupported. The
formalization rule can be represented, but its projection must refuse until the exact
modelo mapping is grounded. Later filing years require their own supported design.

## Sources

- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:1314-1319`
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:1673-1678`
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:1786-1788`
- `src/cadrumo/_data/corpus/normatives/html/rd-634-2015.html.extracted.md:1021-1026`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/01-193-orden-eha-3377-2011-actualizado-por-orden-hac-1430-2025-de-3-de-diciembre-357-kb-pdf.pdf.extracted.md:851-935`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.extracted.md:110-114`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.extracted.md:203-275`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.extracted.md:306-439`
- `src/cadrumo/locales/es/modelo/schema/180.yml:16-67`
