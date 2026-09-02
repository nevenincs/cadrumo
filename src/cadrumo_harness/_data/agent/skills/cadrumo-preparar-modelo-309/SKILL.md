---
name: cadrumo-preparar-modelo-309
description: >-
  Prepare a Modelo 309 (IVA declaración-liquidación no periódica) from a
  classified ledger: create the work unit, calculate the ad-hoc IVA cuota,
  verify, export the fichero-BOE, and hand off for the taxpayer to file. Use
  when the taxpayer has a one-off, non-periodic IVA trigger outside their
  normal filing schedule (or has no periodic IVA obligation at all).
applies_when:
  profile_facts:
    - fact: iva_regime
      match: equals
      values: [RECARGO_EQUIVALENCIA, EXENTO, REAGP, NO_APLICA]
---

# Prepare Modelo 309

Modelo 309 is the ad-hoc IVA declaration for a non-periodic obligation trigger:
an intracommunity acquisition of a new means of transport (or similar
inversión-del-sujeto-pasivo event) under régimen especial de la agricultura, or
a recargo-de-equivalencia retailer's devolución claim on traveler exports. The
CLI computes the cuota from the classified ledger; you orchestrate and relay.
Never compute a casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-303`: the lifecycle spine (work
create → calculate → verify → revision review → export → reconcile) is
identical. The delta is the trigger condition (an ad-hoc event, not a
recurring period), the period token (`AD-HOC`, not `1T`-`4T`), and a smaller,
single-formula casilla shape.

## When Modelo 309 applies, not Modelo 303

Modelo 309 is for a taxpayer who does NOT have a standing periodic IVA
obligation (no régimen general IVA registration) but incurs a one-off IVA
cuota from a specific trigger event. Confirm the trigger before creating the
work unit — do not default to 309 for a taxpayer who already files periodic
303s; a periodic filer routes the same economic event through their next 303
period instead. Ask or confirm which trigger applies:

- Intracommunity acquisition of a new means of transport (medios de transporte
  nuevos) or a similar inversión-del-sujeto-pasivo event.
- Régimen especial de la agricultura, ganadería y pesca event requiring an
  ad-hoc autorepercusión.
- A recargo-de-equivalencia retailer discharging a devolución to a traveler
  (devolución a viajeros).
- Ejecución forzosa proceedings triggering an ad-hoc IVA obligation.

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The ledger transactions for the trigger event are built and classified: IVA
  categories are applied (`aeat app ledger check`,
  `aeat app ledger ratios validate`).
- You know the `filing_year` (the ejercicio the event falls in). The period is
  always the ad-hoc token `AD-HOC` — Modelo 309 has no quarterly or monthly
  variant.

## Procedure

1. Read the form shape: `aeat app modelo describe 309 --year <YEAR>
   --period AD-HOC` and `aeat app modelo casillas 309 --year <YEAR>
   --period AD-HOC`.
2. Create the work unit: `aeat app modelo work create --modelo 309
   --year <YEAR> --period AD-HOC`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`. Read
   `result` and `notices`; every casilla carries `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 309 carries instead of the quarterly pattern

- **Two bound leaves, one computed total** — a much smaller closure than
  Modelo 303's régimen-general shape:
  - `iva.autorepercutido.intracomunitaria` — cuota IVA autorepercutida on the
    intracommunity acquisition trigger (bound from the ledger).
  - `iva.soportado.recargo-equivalencia` — cuota IVA soportado on the
    recargo-de-equivalencia devolución trigger (bound from the ledger).
  - `iva.cuota-no-periodica-total` — **computed**, the sum of the two leaves
    above. This is the sole result casilla; there is no devengado/deducible
    split, no prorrata, and no compensación-pendiente carry (those are
    régimen-general 303 concepts that do not apply to an ad-hoc trigger).
- **No cross-period carry.** Unlike Modelo 390 (which reconciles against four
  prior 303 quarters), a 309 filing stands alone against its trigger event —
  there is no `previous_filing` binding and no inter-modelo relation to a
  prior 309 or 303.
- Only one of the two leaves is typically non-zero for a given trigger (e.g. an
  intracommunity vehicle acquisition populates
  `iva.autorepercutido.intracomunitaria` and leaves
  `iva.soportado.recargo-equivalencia` at zero); both are legitimate on the
  same filing when two distinct ad-hoc triggers land in the same ejercicio.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- `iva.cuota-no-periodica-total` equals the sum of the two bound leaves; act on
  any unconsumed-declarable-IVA advisory the CLI surfaces.
- A filing with both leaves at zero is a red flag — confirm the trigger event
  actually produced a ledger-classified cuota before proceeding; do not export
  a zero-cuota 309 on an unclassified or missing ledger entry.
- Every reported value is quoted verbatim from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id> --format
   json`. Treat exit `1` as a verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is NOT
   official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
