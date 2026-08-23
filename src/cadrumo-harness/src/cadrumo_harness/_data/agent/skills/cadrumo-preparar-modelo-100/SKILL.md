---
name: cadrumo-preparar-modelo-100
description: >-
  Prepare a Modelo 100 (IRPF declaración anual de la renta) from the year's
  classified ledger and profile facts: create the work unit, calculate the
  full cuota chain, verify, export the fichero-BOE, and hand off for the
  taxpayer to file. Use when the taxpayer files their annual personal income
  tax return.
applies_when:
  profile_facts:
    - fact: entity_type
      match: equals
      values: [natural_person]
---

# Prepare Modelo 100

Modelo 100 is the annual IRPF declaración de la renta: the largest and most
structurally complex form the application supports, spanning thousands of
casillas across dozens of sections (rendimientos del trabajo, capital
inmobiliario, capital mobiliario, actividades económicas, ganancias
patrimoniales, base and cuota determination, deducciones autonómicas and
estatales, and more). The CLI computes every casilla; you orchestrate and
relay. Never compute a casilla value yourself, and never enumerate the form's
casilla set from memory - always read it from the registry through the CLI.

This skill diffs against `cadrumo-preparar-modelo-130` and `cadrumo-preparar-modelo-303`: the
lifecycle spine (work create -> calculate -> verify -> revision review ->
export -> reconcile) is identical. The delta is scale (thousands of casillas
across many sections instead of a handful), the annual fold-in of the year's
quarterly Modelo 130/131 pagos fraccionados, a much larger share of
profile-sourced and manually-entered sections alongside the ledger-derived
ones, and the settlement-completeness advisory that guards against a filer
reporting positive taxable income with no computed liability.

## Preconditions

- An active profile exists and carries the taxpayer's personal and family
  facts (marital status, descendientes, discapacidad, comunidad autónoma of
  residence) - `aeat app overview status`.
- Descendientes are declared explicitly with
  `aeat config profile descendiente add` (inspect with
  `aeat config profile descendiente list`, drop one with
  `aeat config profile descendiente remove`). The mínimo por descendientes
  (casillas 0513/0514, LIRPF art. 58/61) and the art. 64/75 anualidades
  separate-escala eligibility are computed from these rows - a taxpayer with
  children whose descendientes are not declared files a larger liability than
  owed, so declare them before calculating.
- The ledger for the full `filing_year` is built and classified where the
  taxpayer has actividades económicas: IRPF categories and business-use
  ratios are applied (`aeat app ledger check`).
- **Every Modelo 130 or Modelo 131 quarter (`1T`-`4T`) for the same
  `filing_year` that the taxpayer was obliged to file is already calculated**
  when the taxpayer carries on an actividad económica under estimación
  directa or estimación objetiva. Modelo 100 folds each quarter's pago
  fraccionado into its own retenciones-and-pagos-a-cuenta casilla; read each
  quarter's revision with `aeat app modelo work revision <work-unit-id>
  --format json` before starting the 100. A taxpayer with no actividad
  económica has no Modelo 130/131 to fold in - do not treat its absence as a
  blocker in that case (see `cross-period dependency suppression is grounded
  in registry classification`, which scopes this fold-in out when the
  taxpayer profile does not declare economic-activity income).
- Any other income-source modelos the taxpayer's profile implies (retenciones
  suffered on Modelo 111/115/123/180/190/193, atribución de rentas on Modelo
  184) are reachable for cross-modelo relation prefill; you do not create
  these yourself, the calculate step resolves them.
- The `filing_year`. The period is always the annual token `0A` - Modelo 100
  has no quarterly variant.

## Procedure

1. Read the form shape before citing any casilla - the registry is the
   authority and the form is far too large to hold in memory:
   `aeat app modelo describe 100 --year <YEAR> --period 0A` and
   `aeat app modelo casillas 100 --year <YEAR> --period 0A`. Narrow a read to
   one casilla or a related group with `--number`, `--form-number`, or
   `--input-kind` (see `aeat app modelo casillas --help`) instead of paging
   through the full set. See `reference/casillas.md` for the section map.
2. Create the work unit: `aeat app modelo work create --modelo 100 --year
   <YEAR> --period 0A`. Read the envelope; note the work-unit id it returns.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`. Every casilla carries `legal_refs` and
   `source_refs` - keep them. Given the form's size, do not attempt to relay
   every casilla to the taxpayer; relay the section totals and any casilla the
   taxpayer specifically asks about, always quoted from this JSON.
4. Read the computed revision:
   `aeat app modelo work revision <work-unit-id> --format json`. This is the
   value set you report to the taxpayer.

## What Modelo 100 adds over the quarterly patterns

- **The pagos-fraccionados fold-in.** The sum of each filed Modelo 130 (or
  131) quarter's casilla `19` for the year folds into Modelo 100 as a pago a
  cuenta, reducing the cuota diferencial. This is a `relation_prefill`
  binding sourced from a `cross_model_output` relation over the four
  quarters, not a value you total by hand - if a quarter is missing or was
  recalculated after the annual filing was created, the fold-in advisory (or
  the calculate step itself) will surface it. Never assert the folded total
  yourself; read it from the calculated casilla.
- **Profile- and manually-sourced sections dominate the form.** Unlike
  Modelo 130/303, where nearly every input is ledger-derived, Modelo 100
  carries large sections resolved from the taxpayer profile (personal and
  family circumstances, mínimo personal y familiar, comunidad autónoma of
  residence for the tramo autonómico) and from operator-entered facts with no
  ledger counterpart (capital inmobiliario for a non-business rented
  property, capital mobiliario, ganancias y pérdidas patrimoniales,
  deducciones autonómicas and estatales, compensación of prior years'
  negative bases). Only the actividades económicas section, where the
  taxpayer has one, is ledger-derived the way Modelo 130/303 are. Route a
  missing profile fact or a missing manual entry to the role that owns it
  (see `cadrumo-operator-orientation-routing`) rather than guessing a value.
- **The cuota chain is long and staged.** Base imponible general and del
  ahorro, base liquidable general and del ahorro, the estatal and autonómica
  escalas, the mínimo personal y familiar at both levels, cuota íntegra,
  cuota líquida, and cuota resultante de la autoliquidación each depend on
  the one before. Read the whole chain from the calculated revision rather
  than re-deriving any intermediate step; the registry's cuota-chain
  construct is what the engine executes.

## Success assertions

Before handing off, confirm in the calculate / revision JSON:

- `status` is `success` (or `warning` with every warning surfaced to the
  taxpayer), never `error`.
- **Settlement completeness (the under-declaration guard).** When the base
  liquidable general casilla is strictly positive, the cuota resultante de la
  autoliquidación casilla must not silently resolve to zero with no declared
  deducción or reducción explaining it. The registry carries a non-blocking
  advisory for exactly this shape (`no-silent-under-declaration`); if the
  calculate or verify step surfaces it, treat it as suspect and ask the
  taxpayer to confirm - a positive taxable base with zero determined
  liability, and no minimo-personal-y-familiar or deducción explanation, is
  the classic silent-under-declaration pattern this form is most exposed to
  given its size. Do not export past this advisory without the taxpayer's
  confirmation.
- **Vivienda-habitual and other transitional deducciones.** A claimed
  deducción that depends on an acquisition or eligibility date (e.g. the
  transitional vivienda-habitual deducción, only available for a dwelling
  acquired before its abolition date) must have the supporting date recorded;
  a claimed deducción with no eligibility signal is an advisory, not a
  silent grant - surface it rather than assume eligibility.
- **Compensación limits.** Any applied compensación of a prior year's
  negative base is bounded both by the stock actually carried from the
  earlier filing and by the current year's computed ceiling; the verify step
  blocks an amount that exceeds either bound. Electing to apply less than the
  maximum is always permitted.
- Every reported casilla value is quoted verbatim from the JSON, with its
  `legal_refs`/`source_refs`.

## Verify and hand off

5. Dispatch the verifier as an independent step:
   `aeat app modelo work verify <work-unit-id> --format json`. Treat exit `1`
   as a verdict; relay every finding, including advisories. Do not export a
   revision that verifies BLOCKED.
6. When verified clean, export the local artefact:
   `aeat app modelo export <work-unit-id>`. This produces a fichero-BOE file.
   It is NOT official AEAT evidence and the return is NOT filed. Tell the
   taxpayer to upload it themselves in the AEAT portal (Renta WEB).
7. After the human files, official evidence is pulled with
   `aeat app modelo reconcile pull` (a justificante), never asserted from the
   local export.
