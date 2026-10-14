---
name: cadrumo-preparar-modelo-200
description: >-
  Prepare a Modelo 200 (Impuesto sobre Sociedades annual return) from the
  entity's booked resultado contable, profile facts and the year's Modelo 202
  pagos fraccionados: create the work unit, calculate the full cuota chain,
  verify, export the local fichero-BOE and hand it to the taxpayer to file.
  Use when a legal entity needs to prepare its annual corporate income tax
  return.
applies_when:
  profile_facts:
    - fact: entity_type
      match: equals
      values: [legal_entity]
---

# Prepare Modelo 200

Modelo 200 is the annual Impuesto sobre Sociedades (IS) self-assessment for a
`legal_entity` taxpayer (Ley 27/2014 LIS) - the sociedad counterpart to Modelo
100's IRPF chain, and a large, multi-section form in its own right (páginas of
balance, cuenta de pérdidas y ganancias, ajustes, compensación de bases
imponibles negativas, deducciones, and the liquidación itself). Cadrumo computes
every casilla; you run the steps and relay the result. Never compute a casilla
value yourself, and never enumerate the form's casilla set from memory - always
read it from the registry.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

This skill shares the lifecycle of `cadrumo-preparar-modelo-100` (the other
large annual form with heavy manual and profile-sourced sections and its own
under-declaration advisory) and `cadrumo-preparar-modelo-303`: work create,
calculate, verify, revision review, export, reconcile. The delta is: the
resultado contable -> base imponible determination is a manual accounting
handoff the engine does not derive from ledger transactions, a chain of advisory
under-declaration guards spanning that handoff, blocking compensación-de-BIN
ceiling gates, an entity-form- and INCN-dispatched tipo de gravamen, and an
annual fold-in of the year's Modelo 202 pagos fraccionados.

## Gating precondition

Modelo 200 applies only to a `legal_entity` taxpayer (LIS, Ley 27/2014) -
never to a natural-person `autonomo`/`attribution_entity` profile, which files
Modelo 100 instead. Confirm applicability from Cadrumo, never from the entity
name alone: `overview.explain` (`aeat app overview explain 200 --year <YEAR>`).
See `cadrumo-pyme-sociedad` for the itinerary that sequences Modelo 200
alongside Modelo 202 and Modelo 303 for a sociedad.

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows an admitted session (`attended` or `key`). With `none`, ask
  the person to hold a live Cadrumo session and review this server's exact
  attendance request, or configure a separately reviewed key. A sign-in alone
  does not grant this server access.
- A profile is active and declares `entity_type = legal_entity`, its
  `legal_entity_form` (sl / sa / sal / sll / sociedad_civil_mercantil /
  cooperativa / sin_fines_lucrativos / other - it selects the tipo de gravamen
  dispatch lane), and its INCN (importe neto de la cifra de negocios) for the
  prior twelve months - read it with `overview.status` (`aeat app overview
  status`). A `new_entity_first_two_profit_periods` flag, when applicable,
  overrides the rate dispatch entirely (LIS art. 29.4, 15%) ahead of the
  INCN-based lanes. A missing profile fact is set with `user-profile.patch`
  (`aeat config profile edit`) once the person has given you the value;
  `describe` lists the question ids it accepts.
- **Every Modelo 202 instalment (`1P`, `2P`, `3P`) for the same `filing_year`
  that the entity was obliged to file is already calculated.** Modelo 200 folds
  the year's pagos fraccionados into the cuota diferencial as a credit. Find
  each instalment's work unit with `modelo.work.list` (`aeat app modelo work
  list`) and read it with `modelo.work.revision` (`aeat app modelo work revision
  --work-unit-id <work-unit-id>`) before starting the 200; a missing or stale
  instalment understates the credit rather than blocking the 200 outright, so
  confirm each one explicitly instead of trusting a zero silently. If an
  instalment is missing, load `cadrumo-preparar-modelo-202`.
- The entity's booked resultado contable (accounting result) for the ejercicio
  is finalised outside this application (cuentas anuales) before Modelo 200 is
  prepared - the base imponible determination starts from that manually
  entered figure (see below); there is no ledger-derived accounting close in
  this application to hand off from.
- The `filing_year`. The period is always the annual token `0A` - Modelo 200
  has no quarterly variant.

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones: the
   `authority` tool with `query` `describe` and then `casillas`, giving
   `modelo` 200, `filing_year` and `period` `0A` (`aeat app modelo describe 200` and
   `aeat app modelo casillas 200`, each with `--year` and `--period`). Both read
   bundled public data. Narrow a read to one casilla or a related group with the `authority` tool's `casilla_number`, `form_number` or `input_kind` (`--number`, `--form-number` or `--input-kind` on the command line) instead of paging through the full set. `reference/casillas.md` gives the section map.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 200 --year <YEAR> --period 0A`). It creates, or reuses, the
   local work unit for that year and sends nothing out. In the result,
   `outcome.kind` is `success` with the work unit under `unit` (`work_unit_id`),
   or `refused` with a `reason`. Report a refusal as it is; do not ask for the
   applicability check to be bypassed unless the person asks.
3. Calculate with `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). It saves a new draft calculation from the profile, the
   manual accounting figures you give it and the folded-in Modelo 202
   instalments; read its input schema with `describe`. Read the result's `calculation_revision_id`, the `calculation` (`casilla_values`,
   `result_summary`, and `observations`, each with its `casilla_id`, `value`,
   `legal_refs` and `source_refs`) and `advisories`. Keep the grounding with
   every value. Given the form's
   size, do not attempt to relay every casilla to the taxpayer; relay the
   liquidación totals and any casilla the taxpayer specifically asks about,
   always quoted from this result.
4. To read the computed revision again without recalculating, use
   `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
   <work-unit-id>`). This is the value set you report to the taxpayer.

## What Modelo 200 adds over the quarterly patterns

- **The resultado contable -> base imponible chain is a manual handoff, not a
  ledger derivation.** Casilla `00500` (resultado de la cuenta de pérdidas y
  ganancias, after IS) and casilla `00501` (resultado antes de Impuesto
  Sociedades - the fiscal-base starting point, `00501` = `00500` + the booked
  IS expense) are both manual inputs describing the entity's finalised cuentas
  anuales. From `00501`, the base imponible casilla `DP200014:00552` is computed
  by applying the year's ajustes extracontables and BIN compensation - never
  re-derive that arithmetic yourself, read it from the calculate step. Ask the
  person for a missing or disputed accounting figure; never assert a resultado
  contable value yourself.
- **A chained sequence of under-declaration advisory guards spans that
  handoff.** Because `00500`, `00501`, and the base imponible are manually
  entered or only partly derived, the registry carries three non-blocking
  advisories at each link:
  - `00500` positive implies `00501` should be nonzero (a positive after-tax
    accounting profit with a zero pre-tax fiscal-base starting point is
    suspect).
  - `00501` positive implies base imponible `DP200014:00552` should be
    nonzero (a positive accounting result resolving to a zero base with no
    declared ajuste or BIN compensation explaining it is suspect).
  - The BIN closing stock (casilla `00671`) should reconcile against the
    roll-forward: opening stock (`00670`) minus BIN applied this period
    (`DP200014:00547`) plus any new BIN generated this period (when the base
    imponible resolves negative).
  Each of these is legitimately zero in some cases (a loss-making year, full
  BIN compensation, correcciones) - the advisories exist so you surface and
  confirm the shape with the taxpayer rather than assume either way. Do not
  export past one of these advisories without that confirmation.
- **Compensación de bases imponibles negativas (BIN) is BLOCKING, not
  advisory.** The applied BIN compensation (casilla `DP200014:00547`) is
  capped by two independent blocking gates (LIS art. 26): it cannot exceed the
  BIN stock available at the start of the period (casilla `00670`), and it
  cannot exceed the art. 26.1 elective ceiling (the greater of 1M EUR or 70%
  of the pre-compensation base, computed as `DP200014:bin-aplicada-maxima`).
  The verify step refuses an amount above either bound; electing to apply
  *less* than the maximum permitted is always legitimate (compensation is a
  right, never a mandate) and never blocks.
- **The tipo de gravamen (casilla `DP200014:00558`) is dispatched by entity
  form and INCN, not a flat rate.** The rate lane is selected in priority
  order: (1) a new-entity override (LIS art. 29.4) - 15% for the first two
  profit-making periods, when the profile flag is set, regardless of
  sub-form; (2) the micro-empresa lane, when the entity's prior-twelve-month
  INCN is below 1.000.000 EUR - a two-tranche bracket schedule for general-
  rate sub-forms (`is.modelo-200.tipo-gravamen-pyme`, LIS DT 44ª: 21%/22% for
  periods initiated in 2025, 19%/21% in 2026), while cooperativas
  fiscalmente protegidas and entidades sin fines lucrativos keep their own
  20%/10% special rates even under this threshold; (3) the ERD art. 101 lane,
  when INCN is below 10.000.000 EUR; (4) the general sub-form lane otherwise
  (25% general, 20% cooperativa, 10% sin fines lucrativos). Casilla `00558` is
  the export-layout rate echo; the cuota íntegra (`DP200014:00562`) is derived
  independently by bracket application, not by multiplying `00558` against the
  base - read both from the calculated revision rather than recomputing either
  one, and never assume a rate from the entity's legal form alone without
  reading the calculated `00558`/`00562` pair.
- **The Modelo 202 pagos-fraccionados fold-in.** The sum of the year's Modelo
  202 instalments folds into Modelo 200 as a credit against the cuota
  diferencial - two mutually exclusive modalidades are both wired (a 202
  filer elects exactly one per LIS art. 40, so the non-elected modalidad's
  relation resolves to zero and never double-counts): casilla `34` (modalidad
  base imponible, art. 40.3) and casilla `03` (modalidad cuota, art. 40.2).
  Both are `relation_prefill` bindings sourced from `cross_model_output`
  relations over the year's instalments, not a value you total by hand - if
  an instalment is missing or was recalculated after the 200 was created,
  the calculate step will surface it. Never assert the folded total yourself;
  read it from the calculated casilla.
- **The cuota chain is staged.** Resultado contable (`00500`/`00501`) -> base
  imponible (`DP200014:00552`) -> cuota íntegra (`DP200014:00562`) -> cuota
  líquida (`DP200014B:00592`) -> cuota diferencial / resultado each depend on
  the one before, with deducciones (doble imposición internacional/interna,
  incentivos de entidad de reducida dimensión) applied along the way. Read
  the whole chain from the calculated revision rather than re-deriving any
  intermediate step.

## Success assertions

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- **Resultado-contable-antes-de-IS determinado.** When casilla `00500`
  (resultado after IS) is strictly positive, casilla `00501` (resultado
  before IS) must not silently resolve to zero. This is the earliest link in
  the under-declaration chain and the one the later base/cuota advisories
  cannot catch on their own, because `00501` is their antecedent.
- **Base imponible determinada cuando el resultado es positivo (the flagship
  under-declaration guard for this form).** When casilla `00501` is strictly
  positive, the base imponible (`DP200014:00552`) must not silently resolve
  to zero with no declared ajuste, compensación, or corrección explaining it.
  A strictly positive `00501` with a zero `DP200014:00552` and no BIN
  compensation, exención, or ajuste extracontable applied is the classic
  silent-under-declaration pattern for this form. Treat the advisory as
  suspect and ask the taxpayer to confirm - do not export past it without
  that confirmation.
- **Compensación de BIN within both caps.** The applied `DP200014:00547` must
  not exceed the art. 26.1 ceiling (`DP200014:bin-aplicada-maxima`) nor the
  opening BIN stock (`00670`). The verify step BLOCKS an amount exceeding
  either; do not attempt to force a value past a blocking finding here -
  correct the applied amount instead.
- **BIN closing-stock continuity.** Casilla `00671` (pending BIN carried to
  future periods) should reconcile against the roll-forward from `00670`,
  `DP200014:00547`, and `DP200014:00552`; a discontinuity is a non-blocking
  advisory worth confirming with the taxpayer before export, since it
  mis-states next year's opening BIN stock otherwise.
- **Dotaciones por deterioro cumplido disponible para integrar.** When the
  cross-year carried "cumplido" dotaciones-por-deterioro stock (casilla
  `01495`) is positive, a zero amount integrated this period (`01496`) is a
  non-blocking advisory, not an error - integrating is the taxpayer's right,
  not a mandate, but a silent zero is worth confirming.
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
   a crash. Do not export a revision that verifies `blocked`. A BIN compensation over either cap will verify `blocked`.
6. When the revision verifies clean, tell the person you are about to export it
   and wait for their go-ahead in the conversation. Then export with
   `modelo.export` (`aeat app modelo export <work-unit-id>`). It writes a fichero-BOE to the
   `output_path` you give, which must be inside the conversation workspace, and
   never contacts the AEAT. Do not replace an existing file unless the person
   asks. The file is NOT official AEAT evidence and the return is NOT filed. Tell
   the taxpayer to upload it themselves in the AEAT portal (Sociedades WEB).
7. After the person says they have filed, load `cadrumo-reconciliar`. Official
   evidence comes from `modelo.reconcile.pull` (`aeat app modelo reconcile
   pull`), which contacts the AEAT read-only to fetch the justificante and
   compare it with the saved calculation. It is never asserted from the local
   export.
