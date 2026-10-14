---
name: cadrumo-preparar-modelo-100
description: >-
  Prepare a Modelo 100 (IRPF annual declaración de la renta) from the year's
  classified ledger and profile facts: create the work unit, calculate the
  full cuota chain, verify, export the local XML file and hand it to the
  taxpayer to file. Use when a natural person needs to prepare their annual
  personal income tax return.
applies_when:
  profile_facts:
    - fact: entity_type
      match: equals
      values: [natural_person]
---

# Prepare Modelo 100

Modelo 100 is the annual IRPF declaración de la renta: the largest and most
structurally complex form Cadrumo supports, spanning thousands of casillas across
dozens of sections (rendimientos del trabajo, capital inmobiliario, capital
mobiliario, actividades económicas, ganancias patrimoniales, base and cuota
determination, deducciones autonómicas and estatales, and more). Cadrumo
computes every casilla; you run the steps and relay the result. Never compute a
casilla value yourself, and never enumerate the form's casilla set from memory -
always read it from the registry.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

This skill shares the lifecycle of `cadrumo-preparar-modelo-130` and
`cadrumo-preparar-modelo-303` (work create, calculate, verify, revision review,
export, reconcile). The delta is scale (thousands of casillas across many
sections instead of a handful), the annual fold-in of the year's quarterly
Modelo 130/131 pagos fraccionados, a much larger share of profile-sourced and
manually-entered sections alongside the ledger-derived ones, the settlement-
completeness advisory that guards against a filer reporting positive taxable
income with no computed liability, and the export format: Modelo 100 exports an
XML file, not a fichero-BOE.

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows a session (`sign_in` or `key`). With `none`, ask the person to
  sign in to Cadrumo.
- A profile is active and carries the taxpayer's personal and family facts
  (marital status, descendientes, discapacidad, comunidad autónoma of
  residence): read it with `overview.status` (`aeat app overview status`) and
  `user-profile.view` (`aeat config profile status`).
- Descendientes are declared explicitly with `user-profile.descendants` (`aeat
  config profile descendiente add`; inspect with `user-profile.view`, `aeat
  config profile descendiente list`; drop one with `aeat config profile
  descendiente remove`, only after you have told the person exactly which one you
  will remove and they have agreed in the conversation). The values come from the
  taxpayer - read the operation's contract with `describe`, or `aeat config
  profile descendiente add --help`, for the fields - and you never invent a birth
  date or a relationship. The mínimo por descendientes (casillas 0513/0514,
  LIRPF art. 58/61) and the art. 64/75 anualidades separate-escala eligibility
  are computed from these rows - a taxpayer with children whose descendientes
  are not declared files a larger liability than owed, so declare them before
  calculating.
- Where the taxpayer has actividades económicas, the ledger for the full
  `filing_year` is built and classified: IRPF categories and business-use
  ratios are applied (`ledger.check`, `aeat app ledger check`). If it is not,
  load `cadrumo-llevar-libro` and then `cadrumo-clasificar`.
- **Every Modelo 130 or Modelo 131 quarter (`1T`-`4T`) for the same
  `filing_year` that the taxpayer was obliged to file is already calculated**
  when the taxpayer carries on an actividad económica under estimación directa
  or estimación objetiva. Modelo 100 folds each quarter's pago fraccionado into
  its own retenciones-and-pagos-a-cuenta casilla. Find each quarter's work unit
  with `modelo.work.list` (`aeat app modelo work list`) and read it with
  `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
  <work-unit-id>`) before starting the 100; if a quarter is missing, load
  `cadrumo-preparar-modelo-130` or `cadrumo-preparar-modelo-131`. A taxpayer
  with no actividad económica has no Modelo 130/131 to fold in - do not treat
  its absence as a blocker in that case; the fold-in is scoped out when the
  profile does not declare economic-activity income.
- Any other income-source modelos the taxpayer's profile implies (retenciones
  suffered on Modelo 111/115/123/180/190/193, atribución de rentas on Modelo
  184) are reachable for cross-modelo relation prefill; you do not create these
  yourself, the calculate step resolves them.
- The `filing_year`. The period is always the annual token `0A` - Modelo 100
  has no quarterly variant.

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones: the
   `authority` tool with `query` `describe` and then `casillas`, giving
   `modelo` 100, `filing_year` and `period` `0A` (`aeat app modelo describe 100` and
   `aeat app modelo casillas 100`, each with `--year` and `--period`). Both read
   bundled public data. Narrow a read to one casilla or a related group with the `authority` tool's `casilla_number`, `form_number` or `input_kind` (`--number`, `--form-number` or `--input-kind` on the command line) instead of paging through the full set. `reference/casillas.md` gives the section map.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 100 --year <YEAR> --period 0A`). It creates, or reuses, the
   local work unit for that year and sends nothing out. In the result,
   `outcome.kind` is `success` with the work unit under `unit` (`work_unit_id`),
   or `refused` with a `reason`. Report a refusal as it is; do not ask for the
   applicability check to be bypassed unless the person asks.
3. Calculate with `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). It saves a new draft calculation from the ledger, the
   profile and the folded-in quarters. Read the result's `calculation_revision_id`, the `calculation` (`casilla_values`,
   `result_summary`, and `observations`, each with its `casilla_id`, `value`,
   `legal_refs` and `source_refs`) and `advisories`. Keep the grounding with
   every value. Given the form's size, do not
   attempt to relay every casilla to the taxpayer; relay the section totals and
   any casilla the taxpayer specifically asks about, always quoted from this
   result.
4. To read the computed revision again without recalculating, use
   `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
   <work-unit-id>`). This is the value set you report to the taxpayer.

## What Modelo 100 adds over the quarterly patterns

- **The pagos-fraccionados fold-in.** The sum of each filed Modelo 130
  quarter's casilla `19` (or Modelo 131 quarter's casilla `15`) for the year
  folds into Modelo 100 as a pago a cuenta, reducing the cuota diferencial.
  This is a `relation_prefill` binding sourced from a `cross_model_output`
  relation over the four quarters, not a value you total by hand - if a quarter
  is missing or was recalculated after the annual filing was created, the
  fold-in advisory (or the calculate step itself) will surface it. Never assert
  the folded total yourself; read it from the calculated casilla.
- **Profile- and manually-sourced sections dominate the form.** Unlike
  Modelo 130/303, where nearly every input is ledger-derived, Modelo 100
  carries large sections resolved from the taxpayer profile (personal and
  family circumstances, mínimo personal y familiar, comunidad autónoma of
  residence for the tramo autonómico) and from taxpayer-entered facts with no
  ledger counterpart (capital inmobiliario for a non-business rented property,
  capital mobiliario, ganancias y pérdidas patrimoniales, deducciones
  autonómicas and estatales, compensación of prior years' negative bases). Only
  the actividades económicas section, where the taxpayer has one, is
  ledger-derived the way Modelo 130/303 are. Ask the person for a missing
  profile fact or manual entry rather than guessing a value; a profile fact is
  set with `user-profile.patch` (`aeat config profile edit`), whose accepted
  question ids and values `describe` lists.
- **The cuota chain is long and staged.** Base imponible general and del
  ahorro, base liquidable general and del ahorro, the estatal and autonómica
  escalas, the mínimo personal y familiar at both levels, cuota íntegra, cuota
  líquida, and cuota resultante de la autoliquidación each depend on the one
  before. Read the whole chain from the calculated revision rather than
  re-deriving any intermediate step; the registry's cuota-chain construct is
  what the engine executes.

## Success assertions

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- **Settlement completeness (the under-declaration guard).** When the base
  liquidable general casilla (`0500`) is strictly positive, the cuota
  resultante de la autoliquidación casilla (`0595`) must not silently resolve to
  zero with no declared deducción or reducción explaining it. The registry
  carries a non-blocking advisory for exactly this shape (`implies_nonzero` on
  `0500` and `0595`, surfaced as a verify finding of kind `advisory`); if the
  calculate or verify step surfaces it, treat it as suspect and ask the
  taxpayer to confirm - a positive taxable base with zero determined liability,
  and no minimo-personal-y-familiar or deducción explanation, is the classic
  silent-under-declaration pattern this form is most exposed to given its size.
  Do not export past this advisory without the taxpayer's confirmation.
- **Vivienda-habitual and other transitional deducciones.** A claimed deducción
  that depends on an acquisition or eligibility date (e.g. the transitional
  vivienda-habitual deducción, only available for a dwelling acquired before
  its abolition date) must have the supporting date recorded; a claimed
  deducción with no eligibility signal is an advisory, not a silent grant -
  surface it rather than assume eligibility.
- **Compensación limits.** Any applied compensación of a prior year's negative
  base is bounded both by the stock actually carried from the earlier filing
  and by the current year's computed ceiling; the verify step blocks an amount
  that exceeds either bound. Electing to apply less than the maximum is always
  permitted.
- Every reported casilla value is quoted verbatim from the result, with its
  `legal_refs` and `source_refs`.

## Verify and hand off

5. Verify with `modelo.work.verify` (`aeat app modelo work verify
   --work-unit-id <work-unit-id>`). It checks the saved draft against the
   requirements for being verified complete and records a verification report
   in the profile. A second run by you is not an independent check, so read the
   result itself: `completeness_status` is `complete`, `incomplete` or
   `blocked`, `granted_verificado_completo` says whether the revision was
   granted, and the findings are in `verification.report.findings`, each with its `kind`,
   `severity` (`blocking` or `warning`), `casilla_id`, `legal_refs` and
   `source_refs`. Relay every finding, including advisories. On the command line, exit `1` is a verdict, not
   a crash. Do not export a revision that verifies `blocked`.
6. When the revision verifies clean, tell the person you are about to export it
   and wait for their go-ahead in the conversation. Then export with
   `modelo.export` (`aeat app modelo export <work-unit-id>`). It writes an XML file to the
   `output_path` you give, which must be inside the conversation workspace, and
   never contacts the AEAT. Do not replace an existing file unless the person
   asks. The file is NOT official AEAT evidence and the return is NOT filed. Tell
   the taxpayer to upload it themselves in the AEAT portal (Renta WEB).
7. After the person says they have filed, load `cadrumo-reconciliar`. Official
   evidence comes from `modelo.reconcile.pull` (`aeat app modelo reconcile
   pull`), which contacts the AEAT read-only to fetch the justificante and
   compare it with the saved calculation. It is never asserted from the local
   export.
