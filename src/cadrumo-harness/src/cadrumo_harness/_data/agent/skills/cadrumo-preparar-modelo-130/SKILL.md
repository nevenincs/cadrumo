---
name: cadrumo-preparar-modelo-130
description: >-
  Prepare a Modelo 130 (IRPF pago fraccionado, estimación directa) from a built
  ledger: create the work unit, calculate, verify, export the fichero-BOE, and
  hand off for the taxpayer to file. Use when the taxpayer is a self-employed
  individual filing their quarterly IRPF instalment.
applies_when:
  profile_facts:
    - fact: irpf_income_categories
      match: contains
      values: [actividad_economica]
    - fact: irpf_estimation_regime
      match: equals
      values: [directa_normal, directa_simplificada]
---

# Prepare Modelo 130

Modelo 130 is the quarterly IRPF instalment (pago fraccionado) for individuals
under direct estimation (estimación directa). The CLI computes it; you orchestrate
and relay. Never compute a casilla value yourself.

## Preconditions

Confirm these before you start; if one is missing, stop and route to the role that
owns it.

- An active profile exists and is unlocked (`aeat app overview status` reports a
  profile).
- The ledger for the quarter is built and classified: incoming and outgoing
  business transactions are imported, with IRPF categories and any business-use
  ratios applied (`aeat app ledger status`, `aeat app ledger check`).
- You know the `filing_year` and the `period` (`1T`, `2T`, `3T`, or `4T`).

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones:
   `aeat app modelo describe 130 --year <YEAR> --period <PERIOD>` and
   `aeat app modelo casillas 130 --year <YEAR> --period <PERIOD>`. See the
   `reference/casillas.md` companion for what each casilla means.
2. Create the work unit:
   `aeat app modelo work create --modelo 130 --year <YEAR> --period <PERIOD>`.
   Read the envelope; note the work-unit id it returns.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`. Read
   `result` and `notices`. Every casilla carries `legal_refs` and `source_refs` -
   keep them.
4. Read the computed revision:
   `aeat app modelo work revision <work-unit-id> --format json`. This is the value
   set you report to the taxpayer.

## Success assertions

Before handing off, confirm in the calculate / revision JSON:

- `status` is `success` (or `warning` with every warning surfaced to the
  taxpayer), never `error`.
- The rendimiento casilla (03) is consistent with declared ingresos (01) minus
  gastos (02); if ingresos are positive but the instalment (07) is zero with no
  declared reduction, treat it as suspect and ask the taxpayer to confirm before
  proceeding (see `cadrumo-operator-grounding`).
- Every reported casilla value is quoted verbatim from the JSON, with its
  `legal_refs`/`source_refs`.

## Verify and hand off

5. Dispatch the verifier as an independent step:
   `aeat app modelo work verify <work-unit-id> --format json`. Treat exit `1` as a
   verdict; relay every finding. Do not export a revision that verifies BLOCKED.
6. When verified clean, export the local artefact:
   `aeat app modelo export <work-unit-id>`. This produces a fichero-BOE file. It is
   NOT official AEAT evidence and the return is NOT filed. Tell the taxpayer to
   upload it themselves in the AEAT portal.
7. After the human files, official evidence is pulled with
   `aeat app modelo reconcile pull` (a justificante), never asserted from the local
   export.
