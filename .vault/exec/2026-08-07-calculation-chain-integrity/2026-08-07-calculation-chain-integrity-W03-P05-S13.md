---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ec858db6fcf18cf96eb77ebaeec0ba105c5f79e59b476a23ca9541c9a8e9af46'
step_id: 'S13'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S13

## Outcome

**Not aggregated, and the reason changed completely.** The blocker this row was waiting on is gone; the row's own premise turned out to be wrong; and two different blockers surfaced on contact, both measured rather than argued.

## The premise is wrong: casilla 08 is not the agrarian volume

Read from the loaded M131 snapshot rather than from the row's assumption, for 2024 and 2025 alike:

| casilla | semantic role | section |
|---|---|---|
| `01` | `irpf_pf_modulos_suma_rendimientos` | actividades económicas estimación objetiva |
| `03` | `irpf_pf_modulos_volumen_sin_datos_base` | actividades sin datos base |
| `05` | `irpf_pf_modulos_volumen_agrario` | actividades agrícolas, ganaderas y forestales |
| `08` | `retenciones_ingresos_a_cuenta` | total liquidación |

The agrarian quarterly volume is **casilla 05**, and it feeds casilla 06 through the 2 % formula. Casilla 08 is retenciones e ingresos a cuenta and has nothing to do with activity volume.

The double-count the row feared is real in shape but between the wrong pair. Casilla 01 is not a volume at all — it is the sum of módulos-computed *rendimientos*, derived from signos and índices correctores rather than from invoices, so no ledger sum could feed it. The pair that could genuinely double-count is `03` against `05`: both are volúmenes de ingresos, differing only by which activities they cover.

## S11's blocker is genuinely cleared

That `03`/`05` split is exactly what the activity axis makes expressible. `W03.P05.S11` landed `tipo_actividad` on the transaction, so agrarian rows can now be separated from the rest instead of feeding both casillas. Had the two new blockers not existed, this row would have been unblocked.

## Blocker one: the base excludes what the ledger cannot see

RD 439/2007 art. 110.1.c), verbatim from the bundled corpus:

> Tratándose de actividades agrícolas, ganaderas, forestales o pesqueras, cualquiera que fuese el método de determinación del rendimiento neto, el 2 por ciento del **volumen de ingresos del trimestre, excluidas las subvenciones de capital y las indemnizaciones**.

The ledger carries no marker for either. Sweeping all 42 spending categories returns nothing matching `subvenc` or `indemn`, and no IRPF category expresses them.

So a binding written today would sum gross incoming agrarian rows including any capital subsidy or indemnity, and produce a casilla 05 larger than the law's base — a silent **over**-declaration. This campaign has been chasing the silent-zero class; this is the same defect with the sign flipped, and it is worse in kind, because an over-declaration costs the taxpayer money that no gate would flag.

## Blocker two: the activity set is art. 110's, not art. 95's

The obvious move is to reuse the `rirpf-art-95:selector-m036-*` parameters `S38` landed. They do not fit, and the mismatch is easy to miss because the two sets overlap heavily.

Art. 110.1.c) covers actividades agrícolas, ganaderas, forestales **o pesqueras**. Art. 95 has no pesquera rate at all, so `B05 Pesquera` is deliberately absent from every art. 95 selector. Reusing the agrícola/ganadera selector for casilla 05 would silently drop a pesquero filer's entire quarterly volume — a silent zero, reintroduced by borrowing the nearest-looking authority.

Casilla 05 needs its own art. 110.1.c) selector, and authoring it raises a question this Step will not guess at: `B04 Producción de mejillón` is listed separately from `B05 Pesquera` in the Modelo 036 table, so AEAT distinguishes them, and whether mejillón production falls inside art. 110's *pesqueras* is a legal determination. Putting a guess in a registry parameter with `legal_refs` attached would give a guess the appearance of grounding.

## What the row needs now

Three things, in order: a way for the ledger to mark subvenciones de capital and indemnizaciones so they can be excluded; an art. 110.1.c) selector parameter with the mejillón question settled against authority; and only then the binding and its resolver.

Nothing was aggregated, and the row stays open. Closing it now would mean shipping a casilla that is wrong in one direction for every agrarian filer receiving a subsidy and wrong in the other for every pesquero filer.
