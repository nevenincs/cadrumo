---
tags:
  - '#adr'
  - '#first-filer-attestation'
date: '2026-06-12'
modified: '2026-06-29'
related:
  - "[[2026-06-12-first-filer-attestation-research]]"
---

# `first-filer-attestation` adr: `censo-grounded activity-start scoping` | (**status:** `superseded`)

> **Superseded by `2026-06-13-first-filer-attestation-adr`.** This ADR's core concept (the activity-start date is genuine AEAT authority and the right axis to scope a first filer's cross-period dependency graph) is retained, but two defects below are corrected by the superseding ADR. (1) Factual grounding: this ADR names AEAT sede procedure G313 as the "Mis Datos Censales" data page. That is wrong - G313 is the certificate-issuance procedure (Expedicion de certificados tributarios, Situacion Censal); the censal form is Modelo 036 (sede code G322); and Mis Datos Censales is a separate data surface. (2) Honesty: the live censo read is non-functional today (never returned a readable censo) and mis-wired to the G313 certificate URL, so this ADR's censo-only, fail-closed posture would permanently trap the first filer it aims to free. The superseding ADR keeps the activity-start axis but sources it from the operator-declared `activity_start_date` now (already trusted by the deadline engine for the same pre-alta suppression), stamped operator-declared with an advisory and censo-corroborated once the live surface is fixed. Read `2026-06-13-first-filer-attestation-adr` for the active decision; everything below is retained for provenance.

## Problem Statement

A business whose first-ever filing is the period in which its economic activity begins cannot file that period locally. The cross-period clean-state gate (`src/aeat/application/calculations/_cross_period_clean_state.py`) demands official AEAT evidence of prior-period filings that, for a genuine first filer, never legally existed. Because local `file` requires a `verified_complete` revision and `verify` blocks on `cross_period_dependency_unclean`, the verify to export to file sequence is a closed loop with no legitimate offline exit.

The research `2026-06-12-first-filer-attestation-research` documents the worked failure case from round-5 operator testing: a business starting activity in 2025 4T truthfully binds `irpf.previous_year_economic_activity_net_income = 0` and `modelo-130-resultados-negativos-anteriores = 0`, yet `work verify` still blocks demanding a Modelo 100 year-2024 filing and a Modelo 130 2025-3T filing that were never owed. Every exit was mapped and confirmed closed: `export` refuses drafts, `file` refuses non-verified revisions, and the only gate-satisfying routes (`live filed pull-sources`, `reconcile file --file`, `filing-record import` with an official evidence kind) all demand official AEAT evidence of a filing the legal world never minted. The import honesty gate is correct to refuse a fabricated evidence id; the defect is not an inconsistent gate but the absence of any vocabulary, anywhere in the architecture, to express that no prior obligation existed.

The research establishes the precise mechanics: `cross_period_dependency_requirements` derives the requirement graph purely from the registry snapshot and never consults taxpayer history or activity-start date. For a first-period filer the prior-period `ModeloRecord` is absent, so `_evaluate_filing_history` appends `MISSING_CURRENT_FILING_RECORD` before evidence is even considered. The gate evaluates the existence of an upstream filing record for every registry-resolved anchor; it does not evaluate the binding value, so a truthful zero still produces a structural anchor that is demanded.

## Considerations

The research grounds the legal reality this ADR depends on. Spanish tax law does not require a first-period filer to have filed anything for periods before activity began. The Modelo 130 obligation arises from carrying on economic activity (RD 439/2007 art. 110, cumulative-from-start-of-activity payment framework); the resultados-negativos-anteriores carry is a same-ejercicio prior-quarter carry only (`max_year_delta = 0`), so a quarter before activity began has no prior saldo to carry: the carry is null, not unevidenced. Current verification on 2026-06-29 rejects the old `RD 439/2007 art. 110.5` premise: the current BOE consolidated art. 110 has no vigente apartado 5, and the casilla 15 mechanics are grounded in AEAT Modelo 130 instructions. The Modelo 100 prior-year-negative carry cites Ley 35/2006 art. 48; a first-year filer has no prior ejercicio that could have generated the saldo.

The real-world evidence that activity started in a given period is the alta de nueva actividad in the censo (Modelo 036/037), which AEAT publishes on the G313 Mis Datos Censales page. The codebase already captures it: `CensoSnapshot.censo_facts` carries the dotted key `censo.activity_start_date`, populated from the live G313 sede read; the snapshot is persisted at IDENTITY sensitivity, content-addressed, and lifecycle-managed, with AEAT documented as the binding legal source of truth and the local profile a cache that must be kept honest. The fact is captured but never consumed by the clean-state gate, the calculation actions, or the overview calendar.

The registry already has a narrow vocabulary for "this anchor is legitimately absent": the M130 `required_period_anchors_for_target` / `_PreviousModeloSelector` machinery treats 1T as producing no anchor (absent-by-design) because the carry is restricted to prior trimestres within the same ejercicio. That absence is keyed on calendar position within the ejercicio, not on the taxpayer activity-start date. The missing concept is an activity-start-scoped absence.

## Constraints

This decision amends an accepted gate and must thread two sibling ADRs without weakening them:

- `2026-06-05-cross-period-filing-clean-state-adr` (accepted) introduced the gate and assumes every cross-period dependency is a real prior obligation. Its fail-closed-when-upstream-filing-history-is-incomplete consequence is exactly what traps the first-period filer. This ADR scopes its requirement graph by activity start.
- `2026-06-05-cross-period-calculation-guards-adr` (accepted) mandates the requirement graph be registry-derived from the selected `RegistrySnapshot` and that callers cannot pass a smaller ad hoc dependency set. The activity-start narrowing here MUST be a grounded narrowing driven by the AEAT censo fact, not an ad hoc caller shrink: this is the load-bearing constraint on the design.

The decision depends on the censo-capture feature (`2026-06-05-live-censo-calendar-reconciliation`, currently with uncommitted edits in the worktree) being the source of `censo.activity_start_date`. That parent feature already pulls the G313 fact; this ADR consumes it. A stale or absent censo snapshot is the principal risk and is handled fail-safe (see Implementation).

This is a proposed decision. It is NOT to be implemented until the operator ratifies it and the open questions below are settled.

## Implementation

Adopt Option A from the research: censo-grounded activity-start scoping, with the registry existing absent-by-design value path materialising the resulting zero.

What data grounds the determination: the activity-start date is read from the ACTIVE `CensoSnapshot` (AEAT-sourced via the G313 sede read), not the free-text profile field. The determination is therefore grounded in AEAT authority rather than operator assertion.

What the gate computes: requirement derivation is taught that a dependency anchor whose period falls strictly before the taxpayer activity-start date is absent-by-design. This generalises the existing M130 1T absent-by-design vocabulary from "calendar position within ejercicio" to "activity-start boundary". A suppressed requirement produces no blocker; the binding value resolves to `Decimal` zero through the existing absent-by-design path. The research leans toward an application-layer filter over the derived requirements (keeping the registry pure and treating the censo as a grounded input) rather than a selector-grammar facet, but pins this as an open question.

What provenance is stamped: a suppressed requirement carries a typed provenance marker naming the censo snapshot id and the activity-start date that scoped it out. The `CrossPeriodDependencyEvidence` row records an explicit no-obligation-pre-activity-period outcome rather than a silent omission, so the removal is declared and auditable. A suppressed pre-activity period has no observation to stamp, so the carry resolves to a provenance-marked zero, not an unstamped carry.

Fail-safe behaviour: when no ACTIVE censo snapshot exists or the activity-start date is blank, the gate fails closed (block, demand a censo pull) rather than falling back to unscoped behaviour or silently opening. The research holds this position; the ADR carries it as an open question for the operator to rule.

Scope boundaries: the scoping applies uniformly to both requirement origins: direct `previous_filing` bindings and registry relations (`relation_source_requirements`). It does not weaken the evidence gate for in-scope periods and leaves `_OFFICIAL_SOURCE_KINDS` and the `app_filing` non-official kind untouched.

Which refusal points this unblocks:

- `verify` (the root fix): the pre-activity dependency is removed from the requirement graph with declared provenance, so the clean-state verdict for a genuinely first period comes back clean and verification proceeds on the merits of the current-period data alone.
- `export` and `file` (unblocked transitively, gates unchanged): both keep their existing refusals; they open only because verify can now legitimately complete. The resulting local filing record still persists its observation under the non-official `app_filing` source kind, so a later dependent period still demands real AEAT evidence of THIS filing.
- `filing-record import`, `reconcile file`, `live filed pull-sources` (deliberately untouched): the official-evidence honesty gates and the `_OFFICIAL_SOURCE_KINDS` set stay exactly as they are. The fix never mints evidence; it removes a demand for evidence of a filing the law never required.

## Rationale

Option A is the only sketch whose no-prior-obligation determination is grounded in AEAT-sourced authority (the G313 censo activity-start date) rather than a forgeable operator claim. It satisfies `aeat-safety-legal-gates` (the determination derives from a regulated authority surface, not user preference), reuses the registry existing absent-by-design vocabulary, and preserves `local-filed-observations-are-non-official-evidence` untouched because it never touches the evidence gate for in-scope periods.

Two alternatives were considered and ranked lower.

- Bare operator attestation (Option B): a verb such as `work attest no-prior-obligation` records a typed non-official observation that the gate treats as satisfying the requirement. The research ranks this lower because nothing structural blocks dishonesty: a bare operator claim could falsely attest away a real prior filing. Its only brake is a non-blocking advisory and a non-official `source_kind`. It has a higher dishonesty surface and weaker legal grounding than A, which `aeat-safety-legal-gates` cautions against (do not treat user preference as authority for regulated calculations).
- Registry-declared first-period semantics (Option C): a selector-grammar facet such as `first_period_yields_zero = true`. The registry is the strongest grounding for a value, but it cannot know which period is a given taxpayer first; it declares carry-forward semantics, not the activity-start boundary. C alone cannot distinguish first-period-for-this-taxpayer from an interior period the taxpayer simply failed to file, and so must combine with A to be safe. Its selector-schema change has broad, registry-wide blast radius. It is best as a complement to A (A scopes which periods are pre-activity; the existing absent-by-design path or C materialises the zero), not as a standalone fix.

## Consequences

The first-period filer gains a legitimate offline path: verify completes on the merits of the current period, export and file open transitively, and the dead end is removed. The fix is narrow: it removes pre-activity periods from the requirement graph before evidence is demanded and records the removal as declared, audited provenance, leaving every official-evidence gate intact.

Dishonesty-resistance analysis. The question this design must answer is: what stops an operator from falsely scoping away a real prior filing? The activity-start date is sourced from the AEAT G313 censo snapshot, which the operator cannot forge without forging an AEAT-signed read; the snapshot is captured by `censo pull` and persisted at IDENTITY sensitivity. A real prior filing that post-dates the alta is still in scope and still demands evidence; only periods genuinely strictly before the alta are suppressed. So an operator cannot scope away a real prior obligation that fell after activity start. The divergence path (a stale or self-declared start date) is closed fail-safe: a missing or stale ACTIVE snapshot blocks and demands a fresh `censo pull` rather than trusting an unverified date, and the admissibility of the free-text `SetupAnswers.activity_start_date` as a fallback is left as an open question precisely because it is weaker authority than the snapshot.

Costs and difficulties. The gate gains a dependency on the censo snapshot being present and fresh, which makes a `censo pull` a precondition for first-period filing; this is an honest cost, not a defect, but it surfaces an operator step that did not previously gate verify. The provenance marker adds a typed outcome to the cross-period evidence surface that downstream consumers (audit, overview) may want to render. The scoping must be applied uniformly across both `previous_filing` and relation-derived requirements or a first filer could be unblocked on one origin and trapped on the other.

Pathways opened. Once activity-start scoping exists as a grounded narrowing, the same censo fact becomes available to the overview calendar (which currently does not consult it) to suppress pre-activity deadline notices, and the absent-by-design provenance shape generalises to any future first-obligation boundary.

Rule-compatibility notes.

- `no-silent-under-declaration`: satisfied. The suppressed requirement is not a silent blank: it is recorded as an explicit no-obligation-pre-activity-period outcome with a typed provenance marker citing the censo snapshot id and activity-start date. The zero is explained, not silently granted. The gate fires declared provenance, not silence.
- `aeat-safety-legal-gates`: satisfied. The determination is grounded in an AEAT authority surface (G313 censo), not operator preference; the gate fails closed on missing or stale authority rather than opening; and no live AEAT write is introduced. This is precisely why Option B (operator-supplied authority) was ranked lower.
- `local-filed-observations-are-non-official-evidence`: satisfied and unchanged. The fix never touches `_OFFICIAL_SOURCE_KINDS` or the `app_filing` kind. The first local filing still persists as non-official `app_filing`, so a later dependent period still demands real AEAT evidence of that filing. The chain for period two onward is not weakened.
- `carried-observations-stamp-their-revision`: satisfied. A suppressed pre-activity period has no observation to carry and therefore nothing to stamp; the value resolves to a provenance-marked zero through the absent-by-design path, not an unstamped carry. The stamping discipline for genuinely carried observations is untouched.

## Open questions for ratification

The research left these open; this ADR carries them for the operator to settle rather than resolving them by fiat.

- Fail-safe on missing or stale censo. When no ACTIVE `CensoSnapshot` exists, or `activity_start_date` is blank, must the gate fail closed (block, demand `aeat config profile censo pull`) rather than fall back to unscoped behaviour? The research position is yes, fail safe; the ADR must rule.
- Snapshot vs. self-declaration. May scoping use the free-text `SetupAnswers.activity_start_date` as a fallback, or is the AEAT-sourced snapshot the only admissible authority? A self-declared field is weaker authority under `aeat-safety-legal-gates`.
- Boundary semantics. Is the period containing the alta date in scope (first partial period equals first obligation) and only strictly prior periods suppressed? M130 cumulative-from-start semantics imply the alta-period itself is the first obligation; the boundary must be pinned against `period-filter-single-boundary-authority`.
- Where scoping lives. Application-layer filter over derived requirements (keeps the registry pure; treats censo as a grounded input) vs. a selector-grammar facet (Option C; broader blast radius). The research leans application-layer.
- Provenance shape. What typed marker records a suppressed pre-activity requirement so it is auditable and not silent: a new non-blocking enum member, or an explicit no-prior-obligation evidence facet citing the censo snapshot id and activity-start date?
- Relation dependencies. The M100 carry arrives via `previous_filing`, but registry relations (`relation_source_requirements`) also feed the graph; confirm the scoping applies uniformly to both origins.

## Codification candidates

- **Rule slug:** `cross-period-scoping-grounded-in-aeat-censo`. **Rule:** A cross-period dependency may be scoped out as no-prior-obligation only when grounded in an AEAT-sourced censo activity-start fact (never a bare operator claim), the gate fails closed on a missing or stale snapshot, and the suppression is recorded as declared provenance rather than a silent blank. (Promote only if this ADR is accepted.)
