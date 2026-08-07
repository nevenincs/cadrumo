---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b5bbd69184d349f7fdf1022b917d83d605f94e099bba06af70e226900e375854'
step_id: 'S38'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S38

## Outcome

**Done.** The code-to-partition correspondence is registry data with its own `legal_refs`, in `registry/aeat/legal/irpf-retencion-actividades.toml`, beside the art. 95 rates it selects. Nothing is inferred in code.

The Step asked for a plan in case the refreshed table proved unable to serve. It serves three of the four boundaries. The fourth is declared as a gap rather than guessed.

## The four entries

| parameter | code set | partition |
|---|---|---|
| `selector-m036-actividades-profesionales` | `A04,A05` | art. 95.1 — 15 % general, 7 % inicio |
| `selector-m036-actividades-agricolas-ganaderas` | `A02,B01,B02` | art. 95.4.2.º — 2 % |
| `selector-m036-actividades-forestales` | `B03` | art. 95.5 — 2 % |
| `selector-m036-...-engorde-porcino-avicultura` | *(empty)* | art. 95.4.1.º — 1 % |

`value` carries the code set and `unit` is `m036-tipo-actividad-code-set`, so the entry is legible as a selector rather than a rate. Both provisions that fix it are cited: RD 439/2007 art. 95 for the partition, Orden EHA/1274/2007 art. 1 for the codes.

## Two mappings that would have been inferences, and are not

**A04 → professional.** The obvious reading is that "Artísticas y Deportivas" is professional because it feels professional. The actual authority is apartado 2.a): *se considerarán comprendidos entre los rendimientos de actividades profesionales: a) En general, los derivados del ejercicio de las actividades incluidas en las Secciones Segunda y Tercera de las Tarifas del IAE*. Sección Segunda is profesionales (`A05`), Sección Tercera is artísticas (`A04`). With that paragraph it is text; without it, it is a guess.

The bundled excerpt stopped at apartado 1 and jumped to apartado 4, so apartados 2 and 3 were fetched from the BOE open-data API and added.

**A02 → agrícola/ganadera.** `A02 Ganadería independiente` sits in the *IAE-subject* table while `B02 Ganadera` sits in the non-subject one, which invites treating them as different partitions. Apartado 4 settles it directly: *Se entenderán incluidas entre las actividades agrícolas y ganaderas: a) La ganadería independiente*. The apartado defines the activity by its nature, not by its IAE subjection.

## The empty set is the point

`A01`, `A03`, `B04` and `B05` select no art. 95 partition and are absent from every entry — arrendamiento retains under art. 100, and resto empresariales, mejillón and pesquera carry no art. 95 rate at all.

The engorde carve-out is different, and that is why it gets an entry with an empty value instead of being left out. Art. 95.4.1.º fixes 1 % for *engorde de porcino y avicultura* specifically; the table's finest ganadero grain is `B02 Ganadera`, with `A02` beside it, and neither isolates porcino or avicultura. Omitting the entry would leave the four-entry file reading as a complete partition of art. 95, and the reading that follows from that is applying the 2 % general rate to an engordador. Declared empty, the gap is visible in the same place a consumer looks for the mapping.

The obvious alternative discriminator is closed too: `S37` bundled AEAT's own statement that the IAE epígrafe is filled *solo* for `A01`–`A05`, so it is never present for a B-series filer.

## Three defects this pass exposed

Grounding work keeps turning up things that were only invisible because nothing checked them.

- `rd-1619-2012:art-6.1.d` was cited from the ledger CLI's simplificada advisory and absent from the catalogue, reddening the production-literal gate. The corpus was already bundled and does support the claim — caso 3.º requires the destinatario NIF for TAI operations by an established issuer — so the entry was added with its sidecar.
- The two `orden-eha-1274-2007` entries, one of which this Step now cites, were grounded on **hand-written paraphrase stubs**, not BOE text. Replaced with the consolidated text from the BOE open-data API.
- That replacement showed what the anchor ratchet was hiding. Both entries declared `#a1`/`#a2`, minted by the extractor's legacy heading fallback, while boe.es publishes this orden's articles under `#ar`/`#ar-2`. **Both citations deep-linked nowhere**, and nothing could catch it, because a stub carrying no anchor at all resolves whatever anchor you ask for. Repointed to the real fragments; the ratchet ceiling drops 90 → 89 to pin it.

The general shape is worth keeping: an unverified anchor is not merely unchecked, it can be wrong, and the two stubs were wrong.

## What this does not do

It declares the correspondence. It does not place the activity-type axis on the ledger, which is `S11`, nor aggregate M131 casilla 08, which is `S13`. Those now have grounded data to build against rather than a missing table.
