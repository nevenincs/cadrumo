---
tags:
  - "#adr"
  - "#first-filer-attestation"
date: '2026-06-13'
related:
  - "[[2026-06-12-first-filer-attestation-research]]"
  - "[[2026-06-12-first-filer-attestation-adr]]"
  - "[[2026-06-05-cross-period-filing-clean-state-adr]]"
  - '[[2026-07-11-censo-operator-manual-enrolment-adr]]'
supersedes:
  - '2026-06-12-first-filer-attestation-adr'
modified: '2026-07-15'
---
# `first-filer-attestation` adr: `operator-declared activity-start scoping (supersedes G313 grounding)` | (**status:** `accepted`)

This ADR **supersedes** `2026-06-12-first-filer-attestation-adr` (now marked
`superseded`). It keeps that ADR's sound concept - the activity-start date is
genuine AEAT authority and is the right axis to scope a first filer's
cross-period dependency graph - but corrects two defects: a factual grounding
error (it named the AEAT certificate procedure G313 as the "Mis Datos Censales"
data page) and an honesty defect (its censo-only, fail-closed design would
permanently trap the very first filer it set out to free). The later accepted
`2026-07-11-censo-operator-manual-enrolment-adr` permanently retired the unsafe
live Censo read. The decision below therefore uses operator-declared activity
start as its only current automated scoping input; it carries no dormant promise
to restore that reader.

## Problem Statement

A business whose first-ever filing is the period in which its economic activity
begins cannot file that period locally. The cross-period clean-state gate
(`src/aeat/application/calculations/_cross_period_clean_state.py`) demands
official AEAT evidence of prior-period filings that, for a genuine first filer,
never legally existed. Local `file` requires a `verified_complete` revision, and
`verify` blocks on `cross_period_dependency_unclean`, so the verify-export-file
sequence is a closed loop with no legitimate offline exit. The research
`2026-06-12-first-filer-attestation-research` maps the worked round-5 failure
case (activity starting 2025 4T, a truthful
`irpf.previous_year_economic_activity_net_income = 0` and
`modelo-130-resultados-negativos-anteriores = 0`, yet `work verify` demands a
Modelo 100 year-2024 filing and a Modelo 130 2025-3T filing that were never
owed) and confirms every exit closed. The defect is the absence of any
vocabulary to express that no prior obligation existed; that diagnosis stands and
is not revised here.

What is revised is the grounding the superseded ADR proposed for the
no-prior-obligation determination, and the practicality of its fail-closed
posture.

### What the superseded ADR got factually wrong

The superseded ADR grounded its Option A on a live read it described as "AEAT
sede G313 Mis Datos Censales", landing
`CensoSnapshot.censo_facts["censo.activity_start_date"]`. This conflates three
distinct AEAT surfaces, confirmed against the authoritative AEAT sede:

- The censal form is Modelo 036 (037 simplified): "Declaracion censal de alta,
  modificacion y baja en el Censo de empresarios, profesionales y retenedores",
  AEAT sede procedure code G322
  (`https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G322.shtml`).
  Filing the 036 alta is what establishes the taxpayer's activity-start date
  (fecha de alta de la actividad).
- G313 is NOT the censal form and NOT a data page. It is "Certificados
  tributarios. Expedicion de certificados tributarios. Situacion Censal"
  (`https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml`) -
  the issuance of a certificate of census situation, governed by RD 1065/2007
  arts. 70-76.
- "Mis Datos Censales" is a separate personal-area surface
  (`https://sede.agenciatributaria.gob.es/Sede/censos-nif-domicilio-fiscal/tramites-censales-relacionados-empresarios-profesionales-retenedores/datos-censales.html`)
  where, with Cl@ve or certificate, a taxpayer consults and modifies their
  activities and their dates - this is where the fecha de alta actually lives as
  consultable data.

The codebase reproduces the error:
`src/aeat/adapters/outbound/aeat/sede/_censo_live.py` hardcodes
`G313_LAUNCHER_URL` to `/Sede/procedimientoini/G313.shtml` (the certificate
procedure) while its docstring labels it "Mis Datos Censales" and its parser
(`src/aeat/adapters/outbound/aeat/sede/_censo.py`) lifts the "Fecha de alta de la
actividad" label from the data-page vocabulary. So the pull points at the
certificate procedure but expects the data page.

### What today's reality forces

A prior verification sweep
(`2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit`) found the live
censo pull has never returned a readable censo for a real profile: every
authenticated `config profile censo pull` that reached AEAT refused with "AEAT
sede G313 returned no readable censo for profile". The only `activity_start_date`
ever populated for a real profile is the operator-typed
`SetupAnswers.activity_start_date` (`src/aeat/core/setup_answers.py:214`,
ISO-8601 validated), which the deadline engine already consumes: `_engine.py:94`
suppresses any obligation whose `closes_on < activity_start_date` (pre-start),
fed from `profile.activity_start_date` at `_profiles.py:150` / `:240`.

Therefore the superseded ADR's "censo-only, fail-closed when no ACTIVE snapshot
exists" posture, applied today, would block the first filer permanently: there is
no functional path to an ACTIVE censo snapshot, so the gate would always fail
closed and the dead end the ADR set out to remove would simply be relocated to a
censo precondition that cannot be met. That is the load-bearing reason for this
revision.

## Considerations

The legal reality is unchanged and remains the foundation. Spanish tax law does
not require a first-period filer to have filed anything for periods before
activity began. The Modelo 130 obligation arises from carrying on economic
activity (RD 439/2007 art. 110, cumulative-from-start-of-activity payment
framework); the resultados-negativos-anteriores carry is a same-ejercicio
prior-quarter carry only (`max_year_delta = 0`), so a quarter before activity
began has no prior saldo - the carry is null, not unevidenced. Current
verification on 2026-06-29 rejects the old `RD 439/2007 art. 110.5` premise: the
current BOE consolidated art. 110 has no vigente apartado 5, and the casilla 15
mechanics are grounded in AEAT Modelo 130 instructions. The Modelo 100
prior-year-negative carry cites Ley 35/2006 art. 48; a first-year filer has no
prior ejercicio that could have generated the saldo.

The activity-start date is genuine, authoritative AEAT data: it is established by
the Modelo 036 alta (G322) and held in the censo, consultable at Mis Datos
Censales and certifiable via G313. The censo-grounding concept is therefore sound
and is retained. What is corrected is (1) the surface/code wiring (G313 is a
certificate procedure, not the data page) and (2) that the AEAT-sourced live read
is non-functional today, so in practice the only available source of the date is
the operator-declared field.

The registry already has a narrow vocabulary for "this anchor is legitimately
absent": the M130 `required_period_anchors_for_target` / `_PreviousModeloSelector`
machinery treats 1T as producing no anchor (absent-by-design) because the carry is
restricted to prior trimestres within the same ejercicio. That absence is keyed
on calendar position within the ejercicio, not on the taxpayer activity-start
date. The missing concept is an activity-start-scoped absence - and the deadline
engine already demonstrates exactly this scoping against the same
operator-declared field.

## Constraints

This decision amends an accepted gate and must thread two sibling ADRs without
weakening them:

- `2026-06-05-cross-period-filing-clean-state-adr` (accepted) introduced the gate
  and assumes every cross-period dependency is a real prior obligation. Its
  fail-closed-when-upstream-filing-history-is-incomplete consequence is exactly
  what traps the first-period filer. This ADR scopes its requirement graph by
  activity start.
- `2026-06-05-cross-period-calculation-guards-adr` (accepted) mandates the
  requirement graph be registry-derived from the selected `RegistrySnapshot` and
  that callers cannot pass a smaller ad hoc dependency set. The activity-start
  narrowing here MUST be a grounded narrowing driven by a declared activity-start
  fact carried on the profile, not an ad hoc per-call shrink: the scoping input is
  the profile's `activity_start_date`, the same field the deadline engine already
  trusts for pre-start suppression - not a parameter a caller invents.

The later accepted `2026-07-11-censo-operator-manual-enrolment-adr` retired the
live Censo scrape because the only discovered data-bearing path is an AEAT
modification tool whose read and write traffic cannot be separated by a
structural safety guard. The superseded first-filer ADR treated that reader as
the source of `censo.activity_start_date`; this ADR does not. The implementable
design uses the operator-declared profile field and preserves its explicitly
non-AEAT provenance. Any future genuine consulta-only endpoint requires a new
ADR; it is not deferred work under this one.

This is a proposed decision. It is NOT to be implemented until the operator
ratifies it and the open questions below are settled.

## Implementation

Adopt activity-start scoping of the cross-period requirement graph, with the
registry's existing absent-by-design value path materialising the resulting zero.
The design is operator-declared and explicitly non-AEAT-corroborated:

What data grounds the determination (today). The activity-start date is read from
the profile's `activity_start_date` - the operator-declared field that the
deadline engine already consumes for pre-start obligation suppression. This is the
only source that is populated in practice. It is stamped with operator-declared
provenance (not AEAT-sourced), and its use carries a non-blocking advisory stating
that the suppression rests on a declared start date. No automatic Censo
corroboration or provenance upgrade exists under the accepted architecture.

What the gate computes. Requirement derivation is taught that a dependency anchor
whose period falls strictly before the taxpayer's activity-start date is
absent-by-design, generalising the existing M130 1T absent-by-design vocabulary
from "calendar position within ejercicio" to "activity-start boundary". A
suppressed requirement produces no blocker; the binding value resolves to
`Decimal` zero through the existing absent-by-design path. The narrowing is
preferably an application-layer filter over the derived requirements (keeping the
registry pure and treating the declared date as a grounded input) rather than a
selector-grammar facet; this is pinned as an open question.

What provenance is stamped. A suppressed requirement carries a typed provenance
marker naming the activity-start date that scoped it out and the
operator-declared provenance kind. The `CrossPeriodDependencyEvidence` row records an explicit
no-obligation-pre-activity-period outcome rather than a silent omission, so the
removal is declared and auditable. A suppressed pre-activity period has no
observation to stamp, so the carry resolves to a provenance-marked zero, not an
unstamped carry.

Behaviour when no activity-start date exists. When the profile carries no
`activity_start_date` at all, the gate fails closed (block, prompt the operator to
record the activity-start date) rather than silently opening. Note the critical
difference from the superseded design: the precondition is a declared date the
operator can supply now, not an AEAT censo snapshot that is unobtainable today.
The first filer is no longer permanently trapped.

Scope boundaries. The scoping applies uniformly to both requirement origins -
direct `previous_filing` bindings and registry relations
(`relation_source_requirements`) - or a first filer would be unblocked on one
origin and trapped on the other. It does not weaken the evidence gate for in-scope
periods and leaves `_OFFICIAL_SOURCE_KINDS` (`aeat_sede_justificante`,
`aeat_sede_live_capture`, `aeat_csv_register`) and the `app_filing` non-official
kind untouched.

Which refusal points this unblocks:

- `verify` (the root fix): the pre-activity dependency is removed from the
  requirement graph with declared provenance, so the clean-state verdict for a
  genuinely first period comes back clean and verification proceeds on the merits
  of the current-period data alone.
- `export` and `file` (unblocked transitively, gates unchanged): both keep their
  existing refusals; they open only because verify can now legitimately complete.
  The resulting local filing record still persists its observation under the
  non-official `app_filing` source kind, so a later dependent period still demands
  real AEAT evidence of THIS filing.
- `filing-record import`, `reconcile file`, `live filed pull-sources`
  (deliberately untouched): the official-evidence honesty gates and the
  `_OFFICIAL_SOURCE_KINDS` set stay exactly as they are. The fix never mints
  evidence; it removes a demand for evidence of a filing the law never required.

## Rationale

The censo-grounding concept the superseded ADR chose was correct in substance -
the activity-start date is real AEAT authority and is the right axis to scope the
dependency graph. It failed on two practical grounds this ADR repairs.

First, it grounded the determination on a live read of "G313 Mis Datos Censales",
which does not exist as described: G313 is the certificate-issuance procedure, the
Modelo 036 (G322) is what sets the alta date, and Mis Datos Censales is the
distinct data surface. Naming the certificate procedure as the data page is a
factual error that propagated into the code wiring.

Second, and decisively, its censo-only fail-closed posture would today trap the
first filer permanently, because the live censo read has never returned a readable
censo and is mis-wired. An ADR whose remedy cannot be satisfied in practice does
not remove the dead end; it relocates it.

The chosen design keeps the sound axis (activity-start) but sources it from the
field that is actually populated - the operator-declared `activity_start_date`,
which the deadline engine already trusts for the pre-alta suppression decision on
the same activity-start axis. The suppression predicate compares the period-span
boundary against the declared date (`period.end_date < activity_start_date`),
rather than the deadline engine's `closes_on < activity_start_date`; because a
period's `end_date` never falls after its `closes_on`, the predicate is strictly
conservative relative to the deadline engine (it suppresses no later than, and
typically earlier than, the deadline-engine comparison would). Reusing the exact
field and a suppression rule on the same axis makes this a consistent,
already-precedented narrowing rather than a novel authority claim. The declared
date is stamped operator-declared with an advisory and is never presented as
AEAT-corroborated. This is the posture that frees the first filer while remaining
consistent with the accepted retirement of the unsafe live Censo reader.

The research's Option C (registry-declared first-period semantics) remains a
complement, not a standalone: the registry declares carry-forward semantics, not
which period is a given taxpayer's first, so it cannot distinguish a true first
period from an interior period the taxpayer simply failed to file. The existing
absent-by-design value path materialises the zero once the activity-start filter
has scoped which periods are pre-activity.

## Consequences

The first-period filer gains a legitimate offline path that is actually reachable
today: verify completes on the merits of the current period, export and file open
transitively, and the dead end is removed without depending on a live censo read
that does not work. The fix is narrow: it removes pre-activity periods from the
requirement graph before evidence is demanded and records the removal as declared,
audited provenance, leaving every official-evidence gate intact.

Dishonesty-resistance analysis (honest, for an operator-declared date). This is
the analysis the superseded ADR could not honestly make, because it assumed an
unforgeable AEAT-signed snapshot that does not exist in practice. The input here
is operator-declared, so the abuse case is real and must be named: an operator
could falsely claim a later alta date to scope away a real prior filing
obligation. The mitigations are:

- A real filing that post-dates the claimed alta is still in scope and still
  demands official evidence - only periods strictly before the declared alta are
  suppressed, so an operator cannot scope away an obligation that fell after the
  claimed start. To hide a real prior obligation, the operator would have to claim
  an alta later than a filing they actually made, which the in-scope evidence
  demand for that later filing still surfaces.
- The suppression is stamped operator-declared (non-AEAT) provenance and carries a
  non-blocking advisory, so the determination is never presented as
  AEAT-authoritative and is visible to any reviewer or audit consumer.
- The advisory keeps the determination honest-but-flagged rather than
  silent-and-trusted. A future independent, safe authority source would require a
  new ADR and an explicit reconciliation contract; this ADR creates no dormant
  reader or compatibility path.

This is weaker authority than an unforgeable snapshot would be - and the ADR says
so plainly rather than claiming a grounding the system cannot deliver today. The
weakness is bounded by the in-scope evidence demand and made non-silent by the
advisory and provenance stamp.

Costs and difficulties. The gate gains a dependency on the profile carrying an
activity-start date, which makes recording that date a precondition for
first-period filing; this is an honest, satisfiable cost (the operator types the
date) rather than the unsatisfiable censo-pull precondition the superseded ADR
implied. The provenance marker adds a typed outcome to the cross-period evidence
surface that downstream consumers (audit, overview) may want to render. The
scoping must be applied uniformly across both `previous_filing` and
relation-derived requirements or a first filer could be unblocked on one origin
and trapped on the other.

Pathways opened. Once activity-start scoping exists as a grounded narrowing, the
same field already feeds the deadline engine's pre-start suppression, so the two
surfaces share one activity-start axis. The absent-by-design provenance shape
generalises to any future first-obligation boundary without depending on a live
Censo reader.

Rule-compatibility notes.

- `no-silent-under-declaration`: satisfied. The suppressed requirement is recorded
  as an explicit no-obligation-pre-activity-period outcome with a typed provenance
  marker and a non-blocking advisory, not a silent blank. The zero is explained.
- `aeat-safety-legal-gates`: partially - and honestly bounded. The determination
  is grounded in a legal reality (no obligation before activity start) and in the
  same declared field the deadline engine already trusts, not in a fabricated
  authority claim. It does NOT claim AEAT-sourced authority for the date today,
  because the accepted architecture has no safe automated Censo read; instead it
  stamps the weaker operator-declared provenance and surfaces an advisory. No live
  AEAT write is introduced.
- `local-filed-observations-are-non-official-evidence`: satisfied and unchanged.
  The fix never touches `_OFFICIAL_SOURCE_KINDS` or the `app_filing` kind. The
  first local filing still persists as non-official `app_filing`, so a later
  dependent period still demands real AEAT evidence of that filing.
- `carried-observations-stamp-their-revision`: satisfied. A suppressed
  pre-activity period has no observation to carry and therefore nothing to stamp;
  the value resolves to a provenance-marked zero through the absent-by-design
  path, not an unstamped carry.

## Open questions for ratification

The research and the superseded ADR left these open; this ADR carries the ones
that remain genuinely open and resolves the censo-vs-self-declaration question
toward operator-declared-now-by-necessity.

- Boundary semantics. Is the period containing the alta date in scope (first
  partial period equals first obligation) and only strictly prior periods
  suppressed? M130 cumulative-from-start semantics imply the alta-period itself is
  the first obligation; the boundary must be pinned against
  `period-filter-single-boundary-authority`.
- Where scoping lives. Application-layer filter over derived requirements (keeps
  the registry pure; treats the declared date as a grounded input) vs. a
  selector-grammar facet (Option C; broader blast radius). The research leans
  application-layer.
- Provenance marker shape. What typed marker records a suppressed pre-activity
  requirement so it is auditable and not silent: a new non-blocking enum member,
  or an explicit no-prior-obligation evidence facet? The later Censo retirement
  removes any snapshot id or corroborated-provenance variant from this choice.
- Relation uniformity. The M100 carry arrives via `previous_filing`, but registry
  relations (`relation_source_requirements`) also feed the graph; confirm the
  scoping applies uniformly to both origins.
- Censo corroboration is not deferred work. The unsafe reader is retired. A
  future genuine consulta-only authority source would require a new ADR and could
  not borrow compatibility or missing-stamp behavior from this decision.

## Censo authority reconciliation

The former G313 launcher/parser path is retired, not an engineering defect to
repair. The accepted `2026-07-11-censo-operator-manual-enrolment-adr` establishes
operator-manual Censo facts and prohibits driving the discovered ZKoss
modification tool as a read path. First-filer scoping therefore consumes only the
operator-declared profile date and preserves its non-official provenance. A
future genuine consulta-only AEAT endpoint would require a new ADR.

## Ratification

The operator ratified this ADR on 2026-06-13 and authorised taking the
recommended default for each open question. The resolved defaults:

- Boundary semantics: the alta-CONTAINING period IS the first obligation; only
  STRICTLY-prior periods are suppressed. Rationale: M130 cumulative-from-start
  semantics make the partial alta-period the first owed return, and the single
  boundary authority (`period-filter-single-boundary-authority`) governs the
  comparison so there is no parallel inclusion override.
- Where scoping lives: an application-layer filter over the derived cross-period
  requirements. Rationale: keeps the registry pure (no selector-grammar facet,
  no per-call ad hoc shrink) and treats the operator-declared activity-start
  date as a grounded input, mirroring how the same field already drives the
  deadline engine's pre-start suppression.
- Provenance marker: an explicit typed no-prior-obligation evidence facet
  carrying operator-declared provenance, NOT a silent omission. Rationale: the
  suppression must be auditable and visible per
  `no-silent-under-declaration`; a typed facet records the scoping decision
  without claiming AEAT corroboration.
- Relation uniformity: the scoping applies uniformly to BOTH `previous_filing`
  bindings and `relation_source_requirements`. Rationale: a first filer must not
  be unblocked on one requirement origin while still trapped on the other.
- Censo-corroboration semantics: retired by the later accepted operator-manual
  Censo decision. The operator-declared `activity_start_date` remains the input,
  with a non-blocking advisory that the suppression rests on a declared date.

## Codification candidates

- Rule slug: `cross-period-scoping-by-declared-activity-start`. Rule: A
  cross-period dependency may be scoped out as no-prior-obligation only when a
  period falls strictly before the taxpayer's recorded activity-start date; the
  determination is stamped with operator-declared provenance and a non-blocking
  advisory, the gate fails closed when no activity-start date is recorded at all,
  and the suppression is recorded as
  declared provenance rather than a silent blank. (Promote only if this ADR is
  accepted.)
- The retired `censo-pull-targets-mis-datos-censales-not-g313-certificate`
  candidate must not be promoted. Current authority forbids restoring the unsafe
  live reader without a new ADR for a genuine consulta-only endpoint.
