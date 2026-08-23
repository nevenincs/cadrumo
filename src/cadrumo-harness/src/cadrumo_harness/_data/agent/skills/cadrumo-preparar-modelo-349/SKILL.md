---
name: cadrumo-preparar-modelo-349
description: >-
  Prepare a Modelo 349 (declaración recapitulativa de operaciones
  intracomunitarias) from the classified ledger: create the work unit,
  calculate the recapitulative listing, verify, review the per-operator and
  per-rectification detail rows, export the fichero-BOE, and hand off for the
  taxpayer to file. Use when the taxpayer's intra-community operations
  (entregas, adquisiciones, servicios, triangulares) require the periodic
  recapitulative declaration.
applies_when:
  profile_facts:
    - fact: does_intracomunitario
      match: is_true
---

# Prepare Modelo 349

Modelo 349 is a **declaración informativa** — a recapitulative listing of the
period's intra-community operations, one row per operator per operation type.
It carries **no cuota, no tipo, and no resultado a ingresar/devolver**: it
reports who was operated with, what kind of operation, and the base amount,
so AEAT can cross-check the VIES network against the operator's periodic IVA
declarations. The CLI computes and lists it; you orchestrate and relay. Never
compute a casilla value yourself, and never describe Modelo 349 as producing a
tax result to the taxpayer — it does not.

This skill diffs against `cadrumo-preparar-modelo-303`: the lifecycle spine (work
create → calculate → verify → revision review → export → reconcile) is
identical, but Modelo 349 has no cuota-bearing casilla, no `annual_summary`
fold-in from another modelo, and no cross-modelo reconciliation equality
gate. Its only fold source is the classified ledger's collectible and payable
invoices carrying an intra-community counterpart; every casilla and detail
row is ledger-derived, with no manual (non-ledger) income block.

## Preconditions

- An active profile exists (`aeat app overview status` reports one) and
  declares an intra-community gating fact (`does_intracomunitario`, or
  `iva.roi_enrolled` / `iva.intracommunity_operations_exceed_50000_eur`) — see
  `cadrumo-intra-community-operator` for the itinerary that routes here.
- The ledger for the period is built and classified: every intra-community
  invoice (issued or received) carries its counterpart country, NIF-IVA, and
  the operation clave AEAT expects (entregas, adquisiciones, servicios,
  triangulares, or a rectification of a prior period) —
  `aeat app ledger check`.
- You know the `filing_year` and the `period`. **Confirm the cadence before
  assuming it**: `aeat app overview explain 349 --year <YEAR>` reads the
  `iva.intracommunity_operations_exceed_50000_eur` profile fact the registry
  uses to pick between the quarterly (`1T`-`4T`) and monthly (`01`-`12`)
  filing schedule — the 50,000 EUR threshold (IVA excluded) shifts Modelo 349
  from quarterly to monthly the moment it is crossed in the reference quarter
  or any of the four preceding natural quarters. Do not assume quarterly
  cadence from a prior period.

## Procedure

1. Read the form shape: `aeat app modelo describe 349 --year <YEAR>
   --period <PERIOD>` and `aeat app modelo casillas 349 --year <YEAR>
   --period <PERIOD>`. See the `reference/casillas.md` companion for what
   each declarante casilla and detail-row field means.
2. Create the work unit: `aeat app modelo work create --modelo 349 --year
   <YEAR> --period <PERIOD>`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla and every detail row carries
   `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 349 is, structurally

- **Four declarante-level summary casillas**, folded directly from the
  period's classified ledger (no cross-modelo fold-in):
  - **Numero total de operadores intracomunitarios** — the count of distinct
    intra-community counterparties across every clave (E entregas, M
    modificaciones a entregas, H adquisiciones triangulares ocultas, A
    adquisiciones, T triangulares, S servicios prestados, I servicios
    recibidos, R referidos por residentes en otros Estados, D devoluciones de
    adquisiciones), excluding rectification rows.
  - **Importe de las operaciones intracomunitarias** — the sum of every such
    operation's base imponible.
  - **Numero total de operadores intracomunitarios con rectificaciones** and
    **Importe de las rectificaciones** — the same two counts, scoped to clave
    C (correcciones) rows only.
- **Per-operator detail rows**, one row per distinct (operator, clave) pair
  for the period: the counterparty's country code, NIF-IVA, apellidos/razón
  social, the operation clave, and the base imponible. These come from the
  same classified-invoice store the declarante totals draw from — do not
  hand-construct or edit a row.
- **Per-rectification detail rows**, one row per distinct (operator, clave,
  rectified period) triple: the same operator identification and clave
  fields, plus the rectified ejercicio and periodo, the corrected base
  imponible, and the base imponible previously declared for that period.
- **Direction-typed sourcing.** Outbound operations (claves E, M, T, S, R —
  operations where the taxpayer issued the invoice) bind from
  `collectible_invoice`; inbound operations (claves A, I, D, H — operations
  where the taxpayer received the invoice) bind from a parallel
  `payable_invoice` binding set. Clave C (correcciones) can correct either
  direction and appears in both binding sets; the runtime de-duplicates by
  operation id when unioning the two directions' rows behind one casilla. A
  suspicious `0` or a missing operator row traces back to the ledger's
  intra-community classification (direction, clave, counterpart country) on
  the source invoice, not to Modelo 349 itself.
- **No cuota, no tipo, no resultado.** Modelo 349 has no casilla equivalent
  to Modelo 303's resultado de la liquidación. Never report a "amount owed"
  or "amount to be refunded" for Modelo 349 — there is none; it is purely
  informational.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- Every declared operator row's clave and direction match the source
  invoice's classification; a nonzero operator count with a zero total
  importe (or vice versa) is the under-declaration shape to question before
  export.
- Every reported declarante casilla and detail row is quoted verbatim from
  the JSON with its grounding — never paraphrased into a tax-due figure.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id>
   --format json`. Modelo 349 has no cross-modelo reconciliation gate (unlike
   Modelo 390/190/193 folding quarterly self-assessments); verification
   checks the recapitulative listing's own internal completeness and
   ledger-consistency. Treat exit `1` as a verdict; do not export a BLOCKED
   revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is
   NOT official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
8. Cross-check with the periodic IVA declaration: the same intra-community
   operations reported here also feed Modelo 303's intracomunitaria
   casillas for the corresponding period. If the taxpayer's Modelo 303 is not
   yet prepared for this period, hand off to `cadrumo-preparar-modelo-303` (or the
   `cadrumo-intra-community-operator` itinerary that sequences both).
