---
tags:
  - '#adr'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - "[[2026-06-12-first-filer-attestation-research]]"
  - "[[2026-06-12-first-filer-attestation-adr]]"
  - "[[2026-06-05-cross-period-filing-clean-state-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace first-filer-attestation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `first-filer-attestation` adr: `operator-declared activity-start scoping, censo-corroborated (supersedes G313 grounding)` | (**status:** `accepted`)

This ADR **supersedes** `2026-06-12-first-filer-attestation-adr` (now marked
`superseded`). It keeps that ADR's sound concept - the activity-start date is
genuine AEAT authority and is the right axis to scope a first filer's
cross-period dependency graph - but corrects two defects: a factual grounding
error (it named the AEAT certificate procedure G313 as the "Mis Datos Censales"
data page) and an honesty defect (its censo-only, fail-closed design would today
permanently trap the very first filer it set out to free, because the live censo
read is non-functional and mis-wired). The decision below is operator-declared
now, censo-corroborated when the live surface is fixed.

## Problem Statement

<!-- Briefly describe the architectural problem or concern.
Describe why the ADR is being persisted. Is this a new feature? Result of an audit? -->

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

<!-- Key factors, constraints, requirements. Tech/libraries considered. -->

The legal reality is unchanged and remains the foundation. Spanish tax law does
not require a first-period filer to have filed anything for periods before
activity began. The Modelo 130 obligation arises from carrying on economic
activity (RD 439/2007 art. 110, cumulative-from-start-of-activity computation);
the resultados-negativos-anteriores carry is a same-ejercicio prior-quarter carry
only (RD 439/2007 art. 110.5; `max_year_delta = 0`), so a quarter before activity
began has no prior saldo - the carry is null, not unevidenced. The Modelo 100
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

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constrainst, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

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

The parent live-censo feature
(`2026-06-05-live-censo-calendar-reconciliation`, currently with uncommitted
edits in the worktree) is NOT a stable dependency today. Its live read is
non-functional (never returned a readable censo) and mis-wired (points at the
G313 certificate procedure, not the Mis Datos Censales data surface). The
superseded ADR treated this feature as the source of `censo.activity_start_date`;
this ADR does not block on it. The implementable design uses the
operator-declared field now and is structured so that, once the live censo
surface is corrected and works, the AEAT-sourced snapshot corroborates and may
upgrade the declared date's provenance - without changing the gate's vocabulary.

This is a proposed decision. It is NOT to be implemented until the operator
ratifies it and the open questions below are settled.

## Implementation

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condense but clear prose that describes functionality layering.

Do not add code (code references must be persisted in separate `{reference}` document. Important `{reference}` snippets must be summarised and referenced explicitly. -->

Adopt activity-start scoping of the cross-period requirement graph, with the
registry's existing absent-by-design value path materialising the resulting zero.
The design is "operator-declared now, censo-corroborated when available":

What data grounds the determination (today). The activity-start date is read from
the profile's `activity_start_date` - the operator-declared field that the
deadline engine already consumes for pre-start obligation suppression. This is the
only source that is populated in practice. It is stamped with operator-declared
provenance (not AEAT-sourced), and its use carries a non-blocking advisory stating
that the suppression rests on a declared start date that has not yet been
corroborated against an AEAT censo snapshot.

What data grounds the determination (when the live surface is fixed). Once a
readable ACTIVE `CensoSnapshot` exists, the gate reconciles the declared date
against the AEAT-sourced `censo.activity_start_date`. A match upgrades the
suppression's provenance from operator-declared to censo-corroborated and clears
the advisory. A divergence surfaces a blocking or advisory contradiction (see open
questions) - the declared date can no longer silently scope when the authority
contradicts it. The gate's vocabulary (the suppressed-requirement marker and its
zero) does not change between the two regimes; only the provenance stamp and
advisory state change.

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
marker naming the activity-start date that scoped it out, the provenance kind
(operator-declared vs censo-corroborated), and - when present - the censo snapshot
id. The `CrossPeriodDependencyEvidence` row records an explicit
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

<!-- Brief rationale why architecture descision was made. Reference `{research}` findings and grounding `{reference}`. -->

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
already-precedented narrowing rather than a novel authority claim. The declared date is stamped operator-declared with
an advisory and is reconciled against - and upgradable to - the AEAT censo
snapshot the moment the live surface is corrected and works. This is
"operator-declared now, censo-corroborated when available", and it is the only
posture that frees the first filer today while keeping a clean upgrade path to
full AEAT corroboration.

The research's Option C (registry-declared first-period semantics) remains a
complement, not a standalone: the registry declares carry-forward semantics, not
which period is a given taxpayer's first, so it cannot distinguish a true first
period from an interior period the taxpayer simply failed to file. The existing
absent-by-design value path materialises the zero once the activity-start filter
has scoped which periods are pre-activity.

## Consequences

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->

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
- Censo corroboration closes the gap structurally once the live read is fixed: a
  divergence between the declared date and the AEAT censo alta contradicts the
  claim and the gate stops trusting the declared date silently. Until then the
  advisory keeps the determination honest-but-flagged rather than
  silent-and-trusted.

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
surfaces share one activity-start axis. When the live censo surface is corrected,
the AEAT snapshot corroborates the same axis with no vocabulary change, and the
absent-by-design provenance shape generalises to any future first-obligation
boundary.

Rule-compatibility notes.

- `no-silent-under-declaration`: satisfied. The suppressed requirement is recorded
  as an explicit no-obligation-pre-activity-period outcome with a typed provenance
  marker and a non-blocking advisory, not a silent blank. The zero is explained.
- `aeat-safety-legal-gates`: partially - and honestly bounded. The determination
  is grounded in a legal reality (no obligation before activity start) and in the
  same declared field the deadline engine already trusts, not in a fabricated
  authority claim. It does NOT claim AEAT-sourced authority for the date today,
  because the AEAT-sourced read is non-functional; instead it stamps the weaker
  operator-declared provenance, surfaces an advisory, and reconciles against AEAT
  authority when available. No live AEAT write is introduced.
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
  requirement so it is auditable and not silent, and how does it carry the
  operator-declared vs censo-corroborated distinction plus the optional censo
  snapshot id: a new non-blocking enum member, or an explicit no-prior-obligation
  evidence facet?
- Relation uniformity. The M100 carry arrives via `previous_filing`, but registry
  relations (`relation_source_requirements`) also feed the graph; confirm the
  scoping applies uniformly to both origins.
- Censo-corroboration semantics (new, deferred). Once the live censo surface is
  fixed, is a declared-vs-censo divergence a blocking contradiction or a
  non-blocking advisory? This mirrors the
  `carried-observations-stamp-their-revision` divergence-blocks / absence-advises
  split but is deferred until the live read works.

## Dependency / follow-up: standalone live-censo wiring defect

Independent of first-filer scoping, the live-censo feature carries a code defect
that must be tracked and fixed on its own track:

- The censo pull (`src/aeat/adapters/outbound/aeat/sede/_censo_live.py`,
  `G313_LAUNCHER_URL`) targets the wrong AEAT surface - the G313 certificate
  procedure (`/Sede/procedimientoini/G313.shtml`, "Expedicion de certificados
  tributarios. Situacion Censal") - while the parser and docstrings expect the
  Mis Datos Censales data page. The pull must be re-pointed at the real Mis Datos
  Censales data surface (the censos-nif-domicilio-fiscal datos-censales endpoint),
  or it must correctly consume a G313 certificate artefact. This is the likely
  cause, alongside the live-auth blocker, of the live read never returning a
  readable censo
  (`2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit`).
- This is a live-censo-feature bug owned by
  `2026-06-05-live-censo-calendar-reconciliation`, NOT by first-filer scoping.
  First-filer scoping must not block on it; it consumes the operator-declared date
  today and corroborates against the censo only once this defect is fixed and the
  live read works.

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
  carrying operator-declared provenance and an optional censo snapshot id, NOT a
  silent omission. Rationale: the suppression must be auditable and visible per
  `no-silent-under-declaration`; a typed facet records the scoping decision and
  carries the operator-declared-vs-censo-corroborated distinction.
- Relation uniformity: the scoping applies uniformly to BOTH `previous_filing`
  bindings and `relation_source_requirements`. Rationale: a first filer must not
  be unblocked on one requirement origin while still trapped on the other.
- Censo-corroboration semantics: deferred. The operator-declared
  `activity_start_date` is the authority NOW, with a non-blocking advisory that
  the suppression rests on a declared-but-uncorroborated date; declared-vs-censo
  divergence handling lands when the live censo read is fixed and works.

## Codification candidates

<!-- If this decision introduces a durable cross-session constraint
that should bind future agents (an obligation, a prohibition, a
discipline that survives this feature's lifecycle), name it here as
a candidate for promotion into a project rule under
`.vaultspec/rules/rules/` via the codify pipeline phase.

Each candidate names the proposed rule slug (kebab-case, naming the
constraint's subject) and a one-sentence statement of the rule.

Not every ADR produces a codification candidate. Decisions that are
local to one feature, or that describe rather than constrain, leave
this section empty. An empty Codification candidates section is a
positive signal, not a failure. -->

- Rule slug: `cross-period-scoping-by-declared-activity-start`. Rule: A
  cross-period dependency may be scoped out as no-prior-obligation only when a
  period falls strictly before the taxpayer's recorded activity-start date; the
  determination is stamped with operator-declared provenance and a non-blocking
  advisory until an AEAT censo snapshot corroborates it, the gate fails closed when
  no activity-start date is recorded at all, and the suppression is recorded as
  declared provenance rather than a silent blank. (Promote only if this ADR is
  accepted.)
- Rule slug: `censo-pull-targets-mis-datos-censales-not-g313-certificate`. Rule:
  The live censo read must target the Mis Datos Censales data surface (or consume a
  G313 certificate artefact correctly), never the G313 certificate-issuance
  procedure URL labelled as a data page. (Promote only if the live-censo wiring fix
  lands.)
