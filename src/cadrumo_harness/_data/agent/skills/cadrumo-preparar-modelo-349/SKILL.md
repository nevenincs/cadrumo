---
name: cadrumo-preparar-modelo-349
description: >-
  Prepare a Modelo 349 (declaración recapitulativa de operaciones
  intracomunitarias) from the classified ledger: create the work unit,
  calculate the listing, review the operator and rectification rows, verify,
  write the local fichero-BOE once the person agrees, and leave the filing to
  the person. Use when intra-community operations require the periodic
  recapitulative declaration.
applies_when:
  profile_facts:
    - fact: does_intracomunitario
      match: is_true
---

# Prepare Modelo 349

Modelo 349 is a **declaración informativa**: a recapitulative listing of the
period's intra-community operations, one row per operator per operation type.
It carries **no cuota, no tipo, and no resultado a ingresar/devolver**: it
reports who the person operated with, what kind of operation, and the base
amount, so AEAT can cross-check the VIES network against the operator's
periodic IVA declarations. Cadrumo computes and lists it; you run the steps and
relay what comes back. Never compute a casilla value yourself, and never
describe Modelo 349 as producing a tax result to the person; it does not.

The lifecycle is the one in `cadrumo-preparar-modelo-303` (work unit, calculate,
verify, revision review, export, reconcile); load that skill to compare. The
differences are that Modelo 349 has no cuota-bearing casilla, takes nothing
from another modelo, and has no cross-modelo reconciliation gate. Its only
source is the classified ledger's issued and received invoices that carry an
intra-community counterpart.

Each step names the tool server operation that does the work and, in
parentheses, the `aeat` command it corresponds to. Use the operation; use the
command only if the tool server cannot do the step. `describe` an operation
before you `execute` it. On the command line the output option goes before the
group: `aeat --format json app modelo work calculate <work-unit-id>`.

## Preconditions

- `status` reports a session that admits this server; you work only inside
  that profile. The profile declares an intra-community gating fact
  (`does_intracomunitario`, or `iva.roi_enrolled` /
  `iva.intracommunity_operations_exceed_50000_eur`); see
  `cadrumo-intra-community-operator` for the itinerary that leads here.
- The ledger for the period is built and classified: every intra-community
  invoice (issued or received) carries its counterpart country, NIF-IVA, and the
  operation clave AEAT expects (entregas, adquisiciones, servicios,
  triangulares, or a rectification of a prior period). Operation `ledger.check`
  (`aeat app ledger check`) reads the ledger and reports anomalies.
- You know the `filing_year` and the `period`. **Confirm the cadence before
  assuming it**: operation `overview.explain` (`aeat app overview explain 349
  --year <YEAR>`) returns `applicable`, `verdict`, `rationale`,
  `scheduling_rationale` and `profile_facts`, including the
  `iva.intracommunity_operations_exceed_50000_eur` fact the registry uses to
  pick between the quarterly (`1T`-`4T`) and monthly (`01`-`12`) schedule. The
  50,000 EUR threshold (IVA excluded) shifts Modelo 349 from quarterly to
  monthly the moment it is crossed in the reference quarter or any of the four
  preceding natural quarters. Do not assume quarterly cadence from a prior
  period.

## Procedure

1. Read the form shape. It reads bundled reference data and changes nothing.
   Tool `authority` with `query` `describe`, then `casillas`, giving `modelo`
   `349`, `filing_year` and `period` (`aeat app modelo describe 349 --year
   <YEAR> --period <PERIOD>` and `aeat app modelo casillas 349 --year <YEAR>
   --period <PERIOD>`). See `reference/casillas.md` for what each declarante
   casilla and detail-row field means.
2. Tell the person you will create the Modelo 349 work unit for that period in
   their profile, then create it: operation `modelo.work.create` (`aeat app
   modelo work create --modelo 349 --year <YEAR> --period <PERIOD>`). Keep the
   work unit id it returns.
3. Tell the person you will save a new draft calculation from their ledger,
   then calculate: operation `modelo.work.calculate` (`aeat app modelo work
   calculate <work-unit-id>`). Read any warning notices and pass them on.
4. Read the computed revision: operations `modelo.work.revision` and
   `modelo.work.revision_snapshot` (`aeat app modelo work revision
   --work-unit-id <work-unit-id>`). The declarante values are the snapshot's
   `casilla_values`, the per-operator and per-rectification rows are its
   `detail_rows` (each with a `row_type` and `fields`), and each casilla's
   `legal_refs` and `source_refs` are in its `observations` (`aeat app modelo
   work observations --work-unit-id <work-unit-id>`).

## What Modelo 349 is, structurally

- **Four declarante-level summary casillas**, folded directly from the period's
  classified ledger (nothing comes from another modelo):
  - **Numero total de operadores intracomunitarios** (`decl.numero-operadores`)
    - the count of distinct intra-community counterparties across every clave
    (E entregas, M modificaciones a entregas, H adquisiciones triangulares
    ocultas, A adquisiciones, T triangulares, S servicios prestados, I
    servicios recibidos, R referidos por residentes en otros Estados, D
    devoluciones de adquisiciones), excluding rectification rows.
  - **Importe de las operaciones intracomunitarias**
    (`decl.importe-operaciones`) - the sum of every such operation's base
    imponible.
  - **Numero total de operadores intracomunitarios con rectificaciones**
    (`decl.numero-rectificaciones`) and **Importe de las rectificaciones**
    (`decl.importe-rectificaciones`) - the same two figures, taken over the
    rectification rows of every clave.
- **Per-operator detail rows**, one row per distinct (operator, clave) pair for
  the period: the counterparty's country code, NIF-IVA, apellidos/razón social,
  the operation clave, and the base imponible. The registry derives them from
  the same classified invoices the declarante totals draw from. The casilla
  list marks these row fields `manual`, so read the revision's `detail_rows` to
  see what actually filled them; do not hand-construct or edit a row.
- **Per-rectification detail rows**, one row per distinct (operator, clave,
  rectified period) triple: the same operator identification and clave fields,
  plus the rectified ejercicio and periodo, the corrected base imponible, and
  the base imponible previously declared for that period.
- **Direction.** Outbound operations (claves E, M, T, S, R: the person issued
  the invoice) come from the issued invoices; inbound operations (claves A, I,
  D, H: the person received the invoice) come from the received invoices. Clave
  C (correcciones) can correct either direction. A suspicious `0` or a missing
  operator row traces back to the ledger's intra-community classification
  (direction, clave, counterpart country) on the source invoice, not to Modelo
  349 itself.
- **No cuota, no tipo, no resultado.** Modelo 349 has no casilla equivalent to
  Modelo 303's resultado de la liquidación. Never report an "amount owed" or
  "amount to be refunded" for Modelo 349; there is none.

## Success assertions

- The calculation raised no warning you have not passed on.
- Every declared operator row's clave and direction match the source invoice's
  classification. A nonzero operator count with a zero total importe (or vice
  versa) is the under-declaration shape to question before export.
- Every declarante casilla and detail row you report is quoted verbatim from
  the revision with its grounding, never paraphrased into a tax-due figure.

## Verify and hand off

5. Verify: operation `modelo.work.verify` (`aeat app modelo work verify
   --work-unit-id <work-unit-id>`). It checks the saved draft and records a
   verification report. Modelo 349 has no cross-modelo reconciliation gate
   (unlike Modelo 390, 190 and 193, which fold in other filings); verification
   checks the listing's own completeness and ledger consistency. Read
   `completeness_status` (`complete`, `incomplete` or `blocked`), every entry of
   `findings` (advisories included) and `missing_required_casilla_ids`. The
   command exits `1` for `incomplete` and `blocked`; that is a verdict, not a
   crash. Do not export a `blocked` revision.
6. Say what you are about to do and wait for the person's go-ahead in the
   conversation: you will write a local fichero-BOE for the verified revision
   to a path in the conversation workspace; nothing goes to AEAT. Then
   export: operation `modelo.export` (`aeat app modelo export <work-unit-id>
   --output <path>`). The file is not official AEAT evidence and the return is
   not filed; the person uploads it themselves in the AEAT portal.
7. After the person says they have filed, tell them you will read the evidence
   AEAT holds (read only on the AEAT side) and compare it with the saved
   calculation, then run operation `modelo.reconcile.pull` (`aeat app modelo
   reconcile pull <work-unit-id>`). Relay the verdict and every difference
   verbatim.
8. Cross-check with the periodic IVA declaration: the same intra-community
   operations reported here also feed Modelo 303's intracomunitaria casillas
   for the corresponding period. If the person's Modelo 303 is not yet prepared
   for this period, load `cadrumo-preparar-modelo-303` (or
   `cadrumo-intra-community-operator`, which sequences both).
