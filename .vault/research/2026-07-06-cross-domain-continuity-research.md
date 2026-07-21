---
tags:
  - '#research'
  - '#cross-domain-continuity'
date: '2026-07-06'
modified: '2026-07-06'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-iva-classification-enrichment-adr]]"
---

# `cross-domain-continuity` research: `iva cash accounting treatment for modelo 303`

This research resolves the W05.P24.S287 planning blockage for W05.P24.S281:
whether Modelo 303 cash-accounting treatment should be modelled as another
`IvaCategory` and whether casilla 62 can be wired alone from the ledger.

## Findings

### Existing vault decisions

The accepted `2026-05-27-iva-classification-enrichment-adr` already formalises
the four intracom/export decisions requested by the original W05.P24.S287 text:
`iva_category` belongs on `Transaction`, `BusinessClassification` remains a
business/personal gate, casilla 62 is out of intracom/export scope, and R12 B2B
services to EU customers are not folded into casilla 59. That ADR deliberately
defers criterio de caja to S281 rather than deciding it.

RAG grounding used before this note:

- `uvx vaultspec-rag search "criterio de caja casilla 62 Ley 37/1992 art 163 quinquies Modelo 303 aggregation" --type code`
- `uvx vaultspec-rag search "criterio de caja casilla 62 Ley 37/1992 art 163 quinquies Modelo 303 aggregation" --type vault --doc-type adr,plan,audit,exec`
- `uvx vaultspec-rag search "Modelo 303 criterio de caja casillas 62 63 74 75 Ley 37/1992 163 quinquiesdecies" --type vault --doc-type adr,plan,audit,exec`
- `uvx vaultspec-rag search "criterio caja casilla 62 63 74 75 manual input Modelo 303" --type code`

### Legal grounding

Bundled corpus `src/aeat/_data/corpus/normatives/html/ley-37-1992.html.extracted.md`
contains the relevant consolidated LIVA text:

- Art. 75 defines the general devengo timing for deliveries and services.
- Art. 163 decies-undecies define eligibility and election for the special
  cash-accounting regime.
- Art. 163 duodecies excludes specific operations from the regime, including
  arts. 21 and 25 exempt exports and intra-community deliveries, acquisitions,
  reverse-charge cases, imports, and other listed categories.
- Art. 163 terdecies changes devengo and deduction timing for taxpayers using
  the regime: output VAT is due on total or partial collection, or on 31 December
  of the following year if unpaid; input deduction arises on payment, or the same
  fallback date if unpaid.
- Art. 163 quinquiesdecies applies payment-timed deduction to non-regime
  recipients of operations affected by the regime.

Live official cross-checks on 2026-07-06:

- BOE consolidated Ley 37/1992 at `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740`
  confirms art. 21 exports, art. 25 intra-community supplies, art. 75 devengo,
  and the cash-accounting regime articles.
- AEAT "Criterio de caja - Obligaciones formales" at
  `https://sede.agenciatributaria.gob.es/Sede/iva/regimenes-tributacion-iva/criterio-caja/obligaciones-formales.html`
  says Modelo 303 must include VAT accrued under cash accounting and, as
  information, total operations as if the general devengo rule had applied.
- The official Modelo 303 form PDF at
  `https://www.hacienda.gob.es/SGT/NormativaDoctrina/main/main_2017/anexo%20v%20-%20modelo%20303.pdf`
  labels boxes 62/63 as supplies to which the regime was applied that would
  have accrued under art. 75, and boxes 74/75 as acquisitions to which the regime
  applies or by which it is affected.

### Registry and code state

The two M303 registry revisions declare boxes 62, 63, 74, and 75 as optional
manual informational rows:

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/casillas/0001-casillas.part-002.toml`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`

Their current legal refs are generic IVA/form refs (`art-88`, `art-92`,
`rd-1624-1992:art-71`, `orden-eha-3786-2008:art-1`). The registry legal
catalogue currently has no `ley-37-1992:art-75` entry and no cash-accounting
entries for `art-163-decies` through `art-163-quinquiesdecies`. S281 must not
add a filing-grade binding while those legal refs remain generic.

### Decision pressure

`IvaCategory` is the wrong axis for criterio de caja. Cash accounting does not
replace the operation's IVA treatment; it changes when VAT is accrued or deducted
and requires additional informational reporting. A cash-accounting sale can still
be a domestic general-rate sale, and the regime explicitly excludes intracom and
export categories that the existing enum already models. Encoding the regime as
an `IvaCategory` member would erase the real tax category or require parallel
category encodings.

The implementation decision should therefore introduce independent cash-accounting
metadata and payment evidence, then project both the settlement effect and the
informational boxes. Wiring only casilla 62 would be structurally incomplete:
boxes 62/63 form the supply base/cuota pair and boxes 74/75 form the acquisition
base/cuota pair for recipient-side affected operations.
