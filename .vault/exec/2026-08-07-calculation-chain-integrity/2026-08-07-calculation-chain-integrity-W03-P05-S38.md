---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8096c9d3b3bd4aff873d1ae9b5af093d9ecf7c30fb38386d027c44ac5ce955e7'
step_id: 'S38'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S38

## Outcome

Still gated behind `S37`'s bundling, but the Step's own contingency question is now **answered by evidence rather than left open**: the table partially serves. Three of the four art. 95 boundaries are selectable from it; one is not.

## The table, located and cross-checked

`S37` located the artefact. It is published in the M036 *instrucciones* on the AEAT sede guía práctica, not with the diseño workbook — which is why every sweep of the bundled diseño corpus came back empty. Two independent sede pages carry it identically:

    Código/Tipo de actividad: se cumplimentará de acuerdo con las siguientes tablas.

**Sujetas a IAE:** `A01` Arrendadores de bienes inmuebles · `A02` Ganadería independiente · `A03` Resto empresariales · `A04` Artísticas y deportivas · `A05` Profesionales

**No sujetas a IAE:** `B01` Agrícola · `B02` Ganadera · `B03` Forestal · `B04` Producción de mejillón · `B05` Pesquera

## The prediction this overturns, and the half it confirms

`W03.P04` predicted that any IAE-rooted vocabulary would carry no agrarian value, because agricultural activities are largely IAE-exempt. That reasoning was sound and is **confirmed** — the A-series carries nothing agrarian beyond `A02`.

What it did not anticipate is that the M036 table is not IAE-rooted. It carries a **second series specifically for activities NOT subject to IAE**, and that is exactly where the agrarian values live. So the pessimistic contingency this Step asked me to plan for does not materialise in the form expected.

## Fitness against the four boundaries

| art. 95 boundary | selectable? | from |
|---|---|---|
| professional general 15% | yes | `A04`, `A05` |
| professional inicio 7% | yes | same codes, dated by the taxpayer's start year rather than by activity |
| sectoral 2% (art. 95.4.2.º) | yes | `B01`, `B02`, `B03`, and `A02` |
| **1% carve-out (art. 95.4.1.º)** | **no** | — |

The carve-out is the gap. RD 439/2007 art. 95.4.1.º fixes 1% for **engorde de porcino y avicultura** specifically, and the table's finest ganadera granularity is `B02 Ganadera` plus `A02 Ganadería independiente`. Neither isolates porcino or avicultura, so a taxpayer in that carve-out is indistinguishable from any other livestock filer on this axis alone.

## What that means for the mapping

A grounded code-to-partition mapping can be authored for three boundaries once the table is bundled. The fourth needs a different discriminator — the IAE epígrafe would be the obvious candidate, and `W03.P04` already recorded that `iae_epigraph` is systematically empty for exactly these filers because they are IAE-exempt.

So the honest shape of the eventual mapping is three grounded partitions plus a declared, visible gap for the 1% carve-out — not four partitions, and not a guess at the fourth.

## Why nothing was authored

The codes above come from reading AEAT sede pages, not from a bundled corpus artefact. `legal-grounding-verifies-bundled-authoritative-corpus` requires the mapping be grounded against bundled authoritative text, and a fetched page summary is neither bundled nor verified byte-for-byte. Authoring the registry entries from it would put the mapping one model-read away from its authority, under a rate screen where nothing downstream could detect a misread.

`S37` bundles it; this Step grounds against what is bundled. The sequence stands, but the discovery risk is now retired.
