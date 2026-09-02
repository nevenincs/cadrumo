---
name: cadrumo-preparar-modelo-131
description: >-
  Prepare a Modelo 131 (IRPF pago fraccionado, estimación objetiva / módulos)
  from a built ledger and the taxpayer's módulos data: create the work unit,
  calculate, verify, export the fichero-BOE, and hand off for the taxpayer to
  file. Use when the taxpayer is a self-employed individual filing their
  quarterly IRPF instalment under the objective-estimation (módulos) regime.
applies_when:
  profile_facts:
    - fact: irpf_income_categories
      match: contains
      values: [actividad_economica]
    - fact: irpf_estimation_regime
      match: equals
      values: [objetiva]
---

# Prepare Modelo 131

Modelo 131 is the quarterly IRPF instalment (pago fraccionado) for individuals
under objective estimation (estimación objetiva / módulos) — the counterpart of
Modelo 130 (estimación directa). The CLI computes it; you orchestrate and relay.
Never compute a casilla value yourself.

## Preconditions

Confirm these before you start; if one is missing, stop and route to the role
that owns it.

- An active profile exists and is unlocked (`aeat app overview status` reports a
  profile), and `irpf_estimation_regime` is objetiva
  (`cadrumo-autonomo-modulos` owns that gating predicate).
- The ledger for the quarter is built and classified: incoming and outgoing
  business transactions are imported (`aeat app ledger status`,
  `aeat app ledger check`). Módulos rendimiento is NOT derived from the ledger —
  it is fixed by the annual Orden de módulos tables — but IVA and expense
  evidence for the same activity still needs a classified ledger.
- You know the `filing_year` and the `period` (`1T`, `2T`, `3T`, or `4T`).
- The taxpayer's módulos figures for the period are at hand: the datos-base
  rendimiento (casilla 01) and, where applicable, the sin-datos-base volumen de
  ventas (casilla 03) and the agrarian volumen de ingresos (casilla 05). These
  come from the taxpayer's own módulos worksheet against the year's Orden de
  módulos, not from the ledger and not from you.

## Procedure

1. Read the form shape for the exact filing year so you cite real casillas, not
   remembered ones — the casilla set and which casillas are computed vs manual
   CAN differ by revision year:
   `aeat app modelo describe 131 --year <YEAR> --period <PERIOD>` and
   `aeat app modelo casillas 131 --year <YEAR> --period <PERIOD>`. See the
   `reference/casillas.md` companion for what each casilla means and for the
   revision-year delta.
2. Create the work unit:
   `aeat app modelo work create --modelo 131 --year <YEAR> --period <PERIOD>`.
   Read the envelope; note the work-unit id it returns.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`. Read
   `result` and `notices`. Every casilla carries `legal_refs` and `source_refs` -
   keep them.
4. Read the computed revision:
   `aeat app modelo work revision <work-unit-id> --format json`. This is the
   value set you report to the taxpayer.

## Success assertions

Before handing off, confirm in the calculate / revision JSON:

- `status` is `success` (or `warning` with every warning surfaced to the
  taxpayer), never `error`.
- **The flagship under-declaration risk on this modelo**: casilla `01` ("Suma de
  rendimientos netos") is a manual módulos input because the rendimiento is
  determined externally (the Orden de módulos tables), not by the engine. A
  positive `01` MUST carry a positive `02` ("Pago fraccionado previo por
  datos-base") — the registry's own ADVISORY predicate
  (`modelo-131-<year>-pago-fraccionado-determinado-cuando-rendimientos-positivos`,
  `implies_nonzero(["01", "02"])`) fires exactly this check. If `01` is positive
  and `02` (or the final result `15`) is zero with no declared reduction, treat
  it as suspect and confirm with the taxpayer before proceeding — do not export.
- Casilla `10` ("Diferencia") gates casilla `11` ("Resultados negativos de
  trimestres anteriores"): the registry's BLOCKING_RULE predicate
  (`modelo-131-<year>-c11-cap-by-c10`) refuses a calculation where `11` exceeds a
  strictly positive `10`. A verify BLOCKED on this predicate means the
  prior-quarter negative carry is overstated; do not override it.
- Every reported casilla value is quoted verbatim from the JSON, with its
  `legal_refs`/`source_refs`.

## Verify and hand off

5. Dispatch the verifier as an independent step:
   `aeat app modelo work verify <work-unit-id> --format json`. Treat exit `1` as
   a verdict; relay every finding, including ADVISORY findings — they are not
   errors, but they are never silently dropped (`no-silent-under-declaration`).
   Do not export a revision that verifies BLOCKED.
6. When verified clean, export the local artefact:
   `aeat app modelo export <work-unit-id>`. This produces a fichero-BOE file. It
   is NOT official AEAT evidence and the return is NOT filed. Tell the taxpayer
   to upload it themselves in the AEAT portal.
7. After the human files, official evidence is pulled with
   `aeat app modelo reconcile pull` (a justificante), never asserted from the
   local export.
