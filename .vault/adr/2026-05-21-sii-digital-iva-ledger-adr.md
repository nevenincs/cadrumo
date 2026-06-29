---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-06-29'
related:
  - "[[2026-05-21-taxpayer-type-applicability-adr]]"
  - "[[2026-05-21-taxpayer-type-applicability-plan]]"
  - "[[2026-05-21-taxpayer-type-applicability-research]]"
---


# `cli-workflow-redesign` adr: `SII is modelled as a rolling ledger-submission enrolment, not a periodic-window modelo; it suppresses Modelo 347 and 390 and switches Modelo 303 to monthly` | (**status:** `proposed`)

## Problem Statement

The parent ADR adds a special-enrolment axis to the taxpayer
profile and names the SII model as a child adjudication. The SII
(Suministro Inmediato de Información) is a near-real-time IVA
ledger-submission regime: the four IVA *Libros registro* are kept
at the AEAT Sede by transmitting invoice detail electronically
within a few business days of issuing or recording each invoice.

The codebase cannot represent this. The deadline engine
(`DeadlineEngine`) computes a schedule purely from registry
`deadline_windows` + `filing_schedules` + `applicability_conditions`:
every obligation is a *modelo with a filing window* (opens_on /
closes_on). The SII obligation has no window. It is a *rolling
duty* — every invoice independently starts its own short clock —
and it is continuous, not periodic. There is no obligation class
for it, no enrolment fact to record it, and no way for the
applicability engine to reflect its two structural consequences:
a SII filer is exempt from Modelo 347 and Modelo 390, and a
mandatory-collective SII filer settles IVA monthly rather than
quarterly.

The project owner explicitly flagged SII as outside his own
knowledge. This ADR therefore decides only the *model and the
derivation*, grounds every regulatory claim in BOE/AEAT authority,
and defers — explicitly — the facts that could not be confirmed to
article precision.

## Considerations

- **SII is an enrolment, not a modelo.** It is a census state
  (entered or left via Modelo 036) that re-shapes other
  obligations. It produces no self-assessment document of its own.
  Modelling it as another row in `deadline_windows` would be a
  category error: it has no window, no quarter, no annual cut.
- **The submission duty is rolling and per-invoice.** Each invoice
  must be supplied within four days (business days, excluding
  Saturdays, Sundays and national holidays). Source: AEAT
  "Información general — SII" ("plazo de cuatro días", AEAT Sede,
  confirmed 2026-05-21). This is a different obligation *shape*
  from a filing window and needs its own typed concept.
- **SII membership is derivable, not always declared.** The
  mandatory collective is defined by other facts the profile
  already carries or will carry — gran empresa, REDEME, grupo de
  IVA. The engine should be able to *derive* mandatory SII from
  those facts, while still allowing an explicit voluntary
  enrolment fact for opt-in filers.
- **SII correlates with `large_company`.** The gran-empresa
  threshold (6.010.121,04 €) is the *same* threshold that triggers
  mandatory SII via the monthly-settlement obligation. The parent
  research already notes this correlation; the derivation must not
  treat the two facts as independent.
- **VERI*FACTU is a different regime.** The former combined
  `topics/sii-verifactu.toml` coupled SII with VERI*FACTU
  (RD 1007/2023). VERI*FACTU concerns certified invoicing
  *software*, not the IVA Libros registro. Conflating them into one
  enrolment flag would be wrong. The registry now keeps SII and
  VERI*FACTU as separate topics; this ADR still models only SII.
- **The four-day clock is a business-day calendar.** Computing it
  requires a Spanish national-holiday calendar. The deadline engine
  today only needs window endpoints; a rolling business-day count
  is new calendar capability.

## Constraints

- This ADR decides the *model and derivation only*. No SII
  per-casilla legal text, no XML message schema, and no live
  submission path is decided here. Per the safety-legal-gates
  rule, the app never performs live AEAT submission; SII ledger
  *transmission* is therefore explicitly out of scope — the system
  models the *obligation*, it does not file it.
- Every regulatory claim carries a BOE/AEAT source. Facts that
  could not be confirmed to article precision are listed in
  Consequences as deferred, not asserted.
- The SII enrolment is a typed fact on the special-enrolment axis
  introduced by the parent ADR — a closed enum/model, not free
  text, not a bare boolean buried in `iva`.
- The new rolling-submission obligation class must not be forced
  into the `deadline_windows` shape. It is a sibling obligation
  type, surfaced distinctly by the overview engine.
- Modelo 347 / Modelo 390 suppression and the Modelo 303
  monthly/quarterly periodicity switch are *derived* through
  registry-grounded `applicability_conditions`, each carrying
  `legal_refs`. No suppression is hard-coded in engine logic.
- Per the apex CLI ADR, the CLI root surface stays `config` /
  `app`; the SII obligation is surfaced inside the existing
  `overview` family, not as a new root command.
- VERI*FACTU stays a separate enrolment concept; this ADR does not
  model it and does not merge it with SII.

## Decision / Implementation

### 1. SII as a typed enrolment fact

SII enrolment is modelled on the special-enrolment axis as a typed
fact with three states, not a boolean:

- `not_enrolled` — the taxpayer is not in the SII.
- `mandatory` — in the SII because it belongs to the mandatory
  collective (monthly IVA settlement obligation).
- `voluntary` — opted in via Modelo 036 although not in the
  mandatory collective.

The mandatory collective, per AEAT "Información general — SII" and
"Nuevo sistema de gestión del IVA" (AEAT Sede, confirmed
2026-05-21), is every sujeto pasivo with a *monthly* IVA
self-assessment period:

- **Grandes empresas** — turnover above 6.010.121,04 € in the
  prior year.
- Taxpayers registered in **REDEME** (Registro de Devolución
  Mensual del IVA).
- **Grupos de IVA** (régimen especial del grupo de entidades).
- Fuel/warehouse depot operators — extended to this collective
  from 01/01/2025.

The derivation engine resolves the `mandatory` state from the
profile facts that define that collective (gran empresa via
`large_company`, REDEME enrolment, grupo de IVA). REDEME is not
modelled today and is added alongside SII as a sibling enrolment
fact, because it is one of the mandatory-SII triggers. An explicit
`voluntary` value is recorded only when none of the mandatory
triggers apply — voluntary entrants keep their quarterly
settlement period and must remain in the SII for at least one
calendar year (AEAT "Información general — SII").

When the special-enrolment axis is undeclared, SII state is
`unknown` and the engine reports applicability as *incomplete* per
the parent ADR's safe-default constraint — it never assumes
`not_enrolled`.

### 2. The rolling ledger-submission obligation class

The SII duty is represented as a new obligation class distinct
from the periodic-window modelo. It is a *continuous rolling
obligation*: while SII enrolment is active, the taxpayer carries
an open duty to supply each invoice's record within four business
days of issuing/recording it. Its typed representation declares:

- the regime (SII), its `legal_refs` (RD 596/2016,
  Orden HFP/417/2017 / BOE-A-2017-5312),
- the rolling deadline rule — four days, business-day calendar
  excluding Saturdays, Sundays and national holidays,
- that it has *no filing window* — the overview engine surfaces it
  as a standing obligation, not a dated agenda row.

The deadline engine is extended so the schedule it returns can
carry obligations of this class beside the window-based modelos;
they are not coerced into `deadline_windows`. The business-day
calendar needed to compute the four-day clock is registry data
(Spanish national holidays), grounded the same way the existing
windows are.

### 3. Derived consequences on other modelos

SII enrolment drives three registry-grounded
`applicability_conditions`, each carrying `legal_refs`:

- **Modelo 347 suppressed.** A SII filer is not obliged to file
  the declaración anual de operaciones con terceras personas.
  Source: AEAT "Nuevo sistema de gestión del IVA" — SII filers
  "no están obligados a presentar el modelo 347".
- **Modelo 390 suppressed.** A SII filer is not obliged to file
  the declaración-resumen anual del IVA. Source: same AEAT page;
  the Modelo 390 exemption is given effect through Orden
  HFP/417/2017.
- **Modelo 303 periodicity.** A mandatory-collective SII filer
  settles IVA *monthly*; the SII state is the fact that switches
  Modelo 303 from a quarterly to a monthly schedule for that
  collective. A voluntary SII entrant keeps its quarterly period.

These are registry conditions over the new `entity_type` /
enrolment facts; the engine does not special-case SII in code.

### 4. VERI*FACTU boundary — explicitly out of scope

VERI*FACTU (RD 1007/2023, certified invoicing software) is a
distinct regime and is **not** modelled by this ADR. The registry
now has separate `sii` and `verifactu` topics, so SII and VERI*FACTU
are not exposed as one enrolment. RD 1007/2023 Art. 3 and Disposición
final cuarta now ground the VERI*FACTU population and current dates;
a VERI*FACTU enrolment or profile-behaviour model remains a separate
adjudication.

## Rationale

The deadline engine answers "what do I file, and when?" by walking
filing windows. SII has no window: it is a continuous, per-invoice,
business-day-clocked duty, and it is an enrolment that *removes*
two annual modelos and *changes the cadence* of a third. Forcing
it into the window model would either invent a fake window or drop
the obligation entirely, and either way the overview engine would
keep mis-reporting Modelo 347 and Modelo 390 as applicable to a
SII filer who is in fact exempt from both.

Modelling SII as a typed enrolment, with mandatory membership
*derived* from the facts that legally define the mandatory
collective, keeps the regulatory truth in one place: a profile
that is a gran empresa is, by the same threshold, a mandatory SII
filer, and the engine should not be able to assert one without the
other. Representing the four-day duty as its own obligation class —
rather than a degenerate window — lets the overview surface tell
the operator the truth: this is a standing obligation, not a dated
deadline.

Keeping VERI*FACTU behaviour out is a deliberate boundary: the
registry can now state the current Art. 3 population and final-
provision dates, but merging SII ledger submission with certified
invoicing-software obligations would still bake the wrong regime into
the schema.

## Consequences

- The profile schema gains a typed SII enrolment fact and a
  sibling REDEME enrolment fact on the special-enrolment axis (a
  schema-version bump, executed under the parent plan's Wave W01).
- The deadline engine gains a second obligation class — the
  rolling ledger-submission duty — and a Spanish national-holiday
  business-day calendar to compute its four-day clock. The
  overview engine surfaces it as a standing obligation distinct
  from dated agenda rows.
- The registry gains SII-driven `applicability_conditions`
  suppressing Modelo 347 and Modelo 390 and switching Modelo 303
  to monthly for the mandatory collective, each with `legal_refs`
  (RD 596/2016, Orden HFP/417/2017 / BOE-A-2017-5312).
- Closed 2026-06-29: `topics/sii-verifactu.toml` has been split into
  `topics/sii.toml` and `topics/verifactu.toml`; VERI*FACTU cites
  BOE-keyed RD 1007/2023 article-level entries, not only the document.
- This ADR is a hard prerequisite for any SII enrolment behaviour
  landing under the parent plan (it gates the Wave W01 SII schema
  field and the Wave W03 SII registry rules).

### Deferred — could not be authoritatively grounded here

Per the safety-legal-gates rule, the following were **not**
confirmed to BOE-article precision and must be verified by the
registry track before the corresponding rule is encoded:

- **Exact legal anchor of the Modelo 347 / 390 exemption.** The
  exemption is confirmed by AEAT publications and originates with
  the SII regulation package (RD 596/2016, Orden HFP/417/2017);
  the precise article of the Reglamento del IVA / the Orden that
  fixes each exemption was not transcribed directly. Confirm
  against BOE-A-2017-5312 and the RD 596/2016 RIVA amendments.
- **Four-day clock — precise national-holiday rule.** AEAT states
  "cuatro días" excluding Saturdays, Sundays and national
  holidays; whether regional/local holidays also extend the clock,
  and the exact start event (issue vs registro), were not
  confirmed to article text. Confirm against Orden HFP/417/2017
  before encoding the calendar rule.
- **Fuel/warehouse depot collective (from 01/01/2025).** Confirmed
  as a mandatory-collective extension by AEAT pages; the
  enabling regulation and its exact scope were not read directly.
- **Closed 2026-06-29 — Gran-empresa / SII threshold figure.** The
  registry now cites the regulation that fixes the precise legal
  figure: LIVA Art. 121 (`ley-37-1992:art-121`) for the operation-
  volume calculation and RIVA Art. 71 (`rd-1624-1992:art-71`) for the
  monthly IVA liquidation trigger above **6.010.121,04 euros** in the
  immediately prior calendar year. The `censo.large_company` profile
  field carries both refs; `iva.sii_enrolled` carries RIVA Art. 71
  alongside RD 596/2016.
- **Closed 2026-06-29 — VERI*FACTU population and timeline.** RD
  1007/2023 Art. 3 now grounds the obligated population and
  Disposición final cuarta now grounds the current dates: before
  2027-01-01 for Art. 3.1.a IS taxpayers and before 2027-07-01 for
  the rest of Art. 3.1 obligated taxpayers. A separate ADR is still
  required before any VERI*FACTU enrolment behaviour lands.
- **Voluntary opt-in / opt-out mechanics.** The minimum
  one-calendar-year permanence and Modelo 036 entry are confirmed
  by AEAT; the exact census-declaration timing rules (e.g. the
  November opt-in window) were not confirmed and must be verified.

### Sources

- AEAT — SII, información general:
  `sede.agenciatributaria.gob.es/Sede/iva/suministro-inmediato-informacion/informacion-general.html`
  (consulted 2026-05-21).
- AEAT — Nuevo sistema de gestión del IVA basado en el SII:
  `sede.agenciatributaria.gob.es/Sede/impuestos-tasas/iva/iva-libros-registro-iva-traves-aeat/nuevo-sistema.html`
  (consulted 2026-05-21).
- AEAT — Manual práctico gran empresa, 4.3 SII (gran-empresa
  threshold 6.010.121,04 €):
  `sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-gran-empresa/`
  (consulted 2026-05-21).
- BOE — Orden HFP/417/2017, de 12 de mayo (SII especificaciones
  técnicas): BOE-A-2017-5312, BOE núm. 115, 15 May 2017
  (`boe.es/buscar/act.php?id=BOE-A-2017-5312`).
- BOE — Real Decreto 596/2016, de 2 de diciembre (crea el SII,
  modifica el Reglamento del IVA RD 1624/1992).
- BOE — Real Decreto 1007/2023 (VERI*FACTU / SIF):
  `boe.es/buscar/act.php?id=BOE-A-2023-24840`.
- AEAT — Sistemas Informáticos de Facturación (SIF) y VERI*FACTU:
  `sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu.html`.
