---
tags:
  - '#adr'
  - '#period-revision-resolution'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - "[[2026-06-10-period-revision-resolution-research]]"
---



# `period-revision-resolution` adr: `Period to revision resolution engine` | (**status:** `accepted`)

## Problem Statement

A tax calculation's registry revision is determined by law, never chosen. AEAT publishes
and amends each modelo's norms and form layout per filing period through ordenes
ministeriales, so every `(modelo, filing_year, period)` triple was filed against exactly
one revision. "Which revision applies" is therefore not an input to the calculation
engine; it is a fact the engine must derive. Any calculation path that binds a
hardcoded or externally-chosen revision is a defect — it can compute one year's numbers
under another year's norms.

This overview ADR (operator directive 2026-06-10; Surface 2 of the calculation-engine
foundation, sibling to the calculation-aggregation taxonomy ADR) ratifies the existing
resolution machinery as the single law-determined authority and closes the gaps the
grounding research surfaced. The reassuring headline from that research holds and was
re-verified at HEAD for this ADR: the deterministic resolver `select_revision`
(`src/aeat/domain/calculations/registry/_temporal.py`) already exists, is enforced
unambiguous by the registry non-overlap gate `validate_revision_windows`
(`_validate_revision_rules.py`), and every snapshot funnels through it via
`ValidatedRegistryAuthority.snapshot` → `_build_validated_snapshot`
(`_authority.py`, `_snapshot.py`). No production calculation path hardcodes a revision.

The real gaps this ADR decides on:

- **D1 (identity-vs-calc divergence).** `revision_id` is part of the WorkUnit identity
  key `(bucket_id, modelo, filing_year, period, revision_id)`
  (`src/aeat/domain/modelos/_work_unit.py`) and is persisted at creation, yet every
  calculation path re-resolves the snapshot purely from `filing_year`/`period`
  (`_calculation_actions.py`, `_calculate_input.py`, the `PreviousFilingSourceResolver`
  fallback in `application/calculations/_multi_year.py`) and never consults
  `unit.revision_id`. The creation-time guard `_revision_covers_year`
  (`_work_addressing.py`) checks only **year** coverage, not period coverage and not
  equality with the resolver's pick. An explicit `--revision` naming a revision that
  covers the year but a different period passes the guard and creates a unit whose
  identity claims one revision while calculation silently computes under another — a
  silent legal mismatch.
- **R2 (cross-year carry trust).** Prior-filing carried values are trusted from stored
  `RegistryModeloObservation` records without re-confirming that the source filing's
  revision is the law-determined one. The persisted envelope
  (`_ObservationEnvelopePayload` in
  `src/aeat/application/calculations/_observations_repository.py`) carries **no revision
  identifier at all** — `(modelo, filing_year, period, observations, captured_at,
  source_kind, member_nif)` only — so a wrong/stale-revision prior cannot even be
  detected today, let alone refused.
- **D3/R4 (orden grounding).** The publishing orden that legally fixes a revision's
  applicability sits unstructured inside free-form `legal_refs` (M100 2025 cites
  `orden-hac-277-2026:art-3`; M130 cites `orden-eha-672-2007:art-1`). There is no
  first-class per-revision field naming the orden as the applicability key, so the
  claim "revision X is the legally-correct revision for year Y" is not mechanically
  auditable against BOE.
- **R3 (per-year norm drift inside open-ended revisions).** For `*-y-siguientes`
  revisions, per-year rate/threshold changes are modelled at the parameter-bracket
  layer; a wrong-but-present bracket value is invisible to the resolution engine.

## Considerations

**The resolver's contract, as verified.** `select_revision(modelo, *, filing_year,
period, on=None, revision_id=None)` filters by declared
`period_selector.includes_year(filing_year)`, case-insensitive period membership, an
optional as-of date window, and an optional `revision_id` narrowing — and raises on
zero or more-than-one candidates. Applicability is **declared** in each
`revision.toml` (`valid_from`/`valid_to` + `period_selector`), never inferred from
directory names. `validate_revision_windows` fails the registry load when two
revisions overlap on both date window and period selector, which makes the
unconstrained resolution provably unique in any valid registry.

**A structural property this ADR leans on:** within a valid registry, the
`revision_id` parameter of `select_revision` is *already an assertion, not a selector*.
Narrowing by a revision that genuinely covers `(filing_year, period)` returns the same
revision the unconstrained resolution would (non-overlap guarantees uniqueness);
narrowing by any other revision raises `RegistrySnapshotError`. It is mathematically
impossible for `revision_id` narrowing to *divert* resolution to a different covering
revision. The D1 hole exists only because `_revision_covers_year` re-implements a
weaker (year-only) check instead of delegating to the resolver itself.

**The call-site sweep (closing the research's honest gap).** All production
`authority.snapshot(` call sites were enumerated at HEAD (43 sites outside `tests/`).
Forty pass only caller-context `filing_year` + `period` and let the resolver decide.
Exactly three pass `revision_id`, each benign:

1. `application/calculations/_cross_period_clean_state.py` (dependency inventory) —
   iterates revisions **from the registry itself** filtered by year/period coverage;
   the narrowing is consistent-by-construction with the resolver.
2. `application/filing/runtime.py` (`_snapshot_for_provider`) — a contextless
   schema-browse fallback that synthesises a representative `(year, period)` from the
   latest open revision's own selector and narrows to that same revision;
   consistent-by-construction, and not a calculation-on-a-filing path.
3. `domain/calculations/registry/_scenarios.py` — the scenario replay harness pins the
   revision a fixture declares; by the structural property above the pin either equals
   the law-determined revision or the run refuses.

No site passes a literal or operator-chosen revision into a production calculation.
The remaining literal-looking sites (`diagnostics.py` integrity probe with a named
probe-year constant, `_common.py` and `_projection.py` passing M100's only period
`"0A"`) are period/year context, not revision choices. The research's claim is
confirmed: `select_revision` is the sole resolver (its only production callers are
`_snapshot.py` and `_work_addressing.py`), and no calc path hardcodes a revision.

**Alternatives weighed for D1.**

- *(a) Pass `unit.revision_id` into `authority.snapshot(...)` at calc time.* Rejected
  as the primary mechanism: although narrowing cannot divert within a valid registry,
  it converts a divergence into an opaque "no revision found" refusal rather than an
  instructive "your unit's pinned revision is no longer the law-determined one"
  message, and it normalises the pattern of feeding stored revision ids back into
  resolution — the precedent this ADR exists to forbid.
- *(b) Drop `revision_id` from the WorkUnit identity key.* Rejected: the identity key
  is content-addressed and persisted; ripping the axis out reshapes every stored
  `work_unit_id` for no behavioural gain, and the pinned revision is genuinely useful
  as an audit fact ("what the law said when the unit was created") precisely because
  the registry itself can be corrected after creation.
- *(c) Reconcile-and-assert at both ends (chosen).* Strengthen the creation gate to
  resolver-equality and add a calc-time equality assertion. Divergence then has exactly
  one possible cause — the registry's law-mapping was edited after unit creation — and
  it surfaces as an instructive refusal naming both revisions.

**Precedent.** The CLI operator-surface ADR (`2026-06-10-cli-operator-surface-adr`,
ruling D8) already demoted `preflight --revision-id` from a required handle to a
natural-key default with the explicit id as an exact-replay override that refuses
instructively when stale. This ADR applies the same shape to the registry-revision
axis: natural key `(modelo, filing_year, period)` resolves; an explicit id only
asserts.

**Sibling consistency.** The aggregation-taxonomy ADR (authored in parallel from
`2026-06-10-calculation-aggregation-taxonomy-research`) governs *which mechanism*
populates each engine channel. Every one of those mechanisms — `previous_filing`
bindings, relation fold-ins, ledger aggregation, the IVA wallet decision — consumes a
`RegistrySnapshot` resolved by *this* engine, for the target context and for every
source context (`_relation_prefill.py`, `_binding_prefill.py`, and
`PreviousFilingSourceResolver` all re-resolve source snapshots from the **source's**
year + period, never from a stored revision). The R2 revision-provenance stamp decided
below applies to the carried-observation substrate regardless of which fold-in
mechanism the sibling ADR canonicalises.

## Constraints

- **The non-overlap gate is load-bearing.** Every guarantee in this ADR (unique
  resolution, narrowing-cannot-divert) holds only in a registry that passes
  `validate_revision_windows`. That gate is wired into registry validation
  (`_validate.py`) and runs before any snapshot is served by
  `ValidatedRegistryAuthority`; weakening it voids this ADR. It is hereby ratified as
  a permanent registry invariant.
- **Registry authority flow is the parent surface.** This ADR composes with the
  accepted authority pipeline (TOML → loader → strict schema → validation → authority →
  snapshots); all plug-in points live inside `ValidatedRegistryAuthority`,
  `_snapshot.py`, `_temporal.py`, and the application-layer gates. No new top-level
  surface, per the registry-authority-flow rule.
- **Persisted-record compatibility.** WorkUnits already persist `revision_id` inside a
  content-addressed identity; observations persist with **no** revision field. Both
  decisions below must work against existing stored records: the calc-time assertion
  must handle pre-gate units, and the carry gate must handle unstamped legacy
  observations, without silent acceptance and without bricking historical data.
- **Legal-catalogue dependency for D3.** The first-class orden field is only as
  auditable as the legal catalogue entries it references; the
  registry-calculation-legal-grounding rule (corpus-backed `corpus_ref`, evidence-gate
  cross-check) is the stable parent discipline it rides on.

## Implementation

This is an overview decision, not a plan. Five rulings:

**Ruling 1 — ratify the resolution authority.** `select_revision`, reached exclusively
through `ValidatedRegistryAuthority.snapshot` (or, for work-unit addressing,
`resolve_registry_revision_for_work_target`), is THE single law-determined
period→revision resolver. Production calculation, verification, filing, export, and
projection paths MUST resolve snapshots from caller-context `(modelo, filing_year,
period)` and MUST NOT inject an externally-chosen `revision_id` into resolution. The
`revision_id` parameter on `snapshot`/`select_revision` is reclassified as an
**assertion parameter**: legitimate only for (i) registry-derived enumeration
(`_cross_period_clean_state.py` inventory, `filing/runtime.py` contextless schema
browse) and (ii) fixture/scenario replay pinning — the three swept sites — where it is
consistent-by-construction or refuses. Any new call site passing a stored, literal, or
operator-supplied revision into resolution on a calculation path is a defect.

**Ruling 2 — the D1 contract: reconcile-and-assert at both ends.**

- *Creation end:* `resolve_registry_revision_for_work_target` replaces the weak
  year-only `_revision_covers_year` check with resolver-equality: an explicit
  `--revision` is accepted only when it names exactly
  `select_revision(modelo, filing_year=year, period=period).id`. The natural delegation
  is to call `select_revision(..., revision_id=requested)` and let the structural
  assertion property do the work, then refuse instructively on
  `RegistrySnapshotError` — the refusal MUST name the requested revision, the
  law-determined revision, and state that the binding is fixed by law (per the
  CLI-boundary instructive-refusal mandate in the architecture-boundaries rule).
  `--revision` is thereby demoted from a free override to an idempotence/assertion
  handle, mirroring the operator-surface ADR's D8 shape.
- *Calculation end:* every calc entry that loads a WorkUnit and resolves a snapshot
  from its year + period (`_calculation_actions.py`,
  `_calculate_input.py::_revision_for_work_unit`, and equivalents) adds the equality
  assertion `snapshot.revision.id == work_unit.revision_id` immediately after
  resolution. On divergence — possible only when the registry's law-mapping was
  corrected after the unit was created, or for units persisted before the strengthened
  creation gate — the calculation REFUSES with an error naming both revisions and
  directing the operator to re-create the work unit (the unit's identity is
  content-addressed on the revision axis; it cannot be silently re-pinned). The unit's
  persisted `revision_id` is never passed into resolution; it is only compared against
  resolution's answer.

**Ruling 3 — the R2 carry gate: YES, with a provenance stamp.** The persisted
observation envelope (`_ObservationEnvelopePayload`) gains a revision-provenance field
(the registry revision id the source filing resolved to at capture time; the envelope
docstring explicitly reserved room for such metadata, so the inner
`RegistryModeloObservation` runtime model stays untouched). Every producer (app filing
flow, sede justificante capture, IVA-compensation projection) stamps it at write time
from the snapshot it already holds. At carry-read time
(`resolve_bindings_from_local_store`, the cross-period clean-state evaluation, and the
multi-year resolver), a runtime gate re-confirms
`stamped_revision == select_revision(source_modelo, source_filing_year,
source_period).id`:

- *Divergent stamp* → carry is REFUSED and surfaced as a blocker (the clean-state
  blocker vocabulary already models divergence classes; this adds a
  registry-revision-divergence blocker). A prior filed under one revision must not
  silently propagate its norms into a target period the law binds to another.
- *Missing stamp (legacy record)* → carry proceeds but MUST surface a non-blocking
  ADVISORY finding (the no-silent-under-declaration shape: never a silent grant), so
  legacy data degrades loudly instead of invisibly.

**Ruling 4 — D3 scope: FULL; the orden becomes first-class in this ADR.** Each
`revision.toml` gains a mandatory applicability declaration — working name
`orden_aplicabilidad` (Spanish stem per the naming rule; final field name is the
plan's to confirm) — listing the legal-catalogue ref(s) of the orden(es)
ministerial(es) that approve or amend the modelo form for this revision's window
(e.g. M100 2025 → `orden-hac-277-2026`; M130 2019-y-siguientes → the Orden
HAP/258/2015 lineage its label already names). Registry validation enforces that each
entry (i) resolves in the legal catalogue, (ii) carries a `corpus_ref` to real BOE/AEAT
text per the registry-calculation-legal-grounding rule, and (iii) is also present in
(or merged into) the revision's `legal_refs` so existing snapshot ref-collection and
provenance surfaces carry it automatically. Existing revisions are brought under the
mandate via a hard-cut gate if the backfill is small enough to land atomically,
otherwise a ratcheting gate that forbids new unstamped revisions and burns down the
existing corpus — the plan decides the cut, the obligation itself is not deferred.
Rationale for full scope over deferral: this ADR's central claim is that resolution is
*law-determined*; without the orden as a validated first-class field, that claim is
honor-system — the resolver is deterministic against the registry, but nothing proves
the registry's applicability windows match what AEAT published. Deferring the field
would ratify a mechanism whose legal anchor remains unauditable, which is exactly the
drift shape the legal-grounding rule exists to prevent.

**Ruling 5 — R3 boundary statement.** This ADR's responsibility ends at *structural*
resolution: which revision's casillas, formulas, bindings, and parameters govern a
`(modelo, filing_year, period)`. Per-year norm values **inside** an open-ended
`*-y-siguientes` revision are the parameter-bracket layer's responsibility: temporal
bracket windows, gated for coverage by `validate_bracket_table_temporal_coverage`, and
grounded value-by-value per the registry-calculation-legal-grounding rule. A
wrong-but-present bracket value is a legal-grounding defect, not a resolution defect,
and is out of this ADR's scope — with one connective obligation: an open-ended
revision's `orden_aplicabilidad` must cite the orden establishing the open-ended
applicability, so even the `*-y-siguientes` claim itself is anchored to BOE.

## Rationale

The research (`2026-06-10-period-revision-resolution-research`) found, and this ADR's
own sweep confirmed, that the codebase already implements the operator's legal
principle in its load-bearing core: one resolver, provably unambiguous, behind one
authority funnel, with production calc paths resolving from year + period. The correct
architectural move is therefore ratification plus gap-closure, not redesign.

D1 is decided as reconcile-and-assert (not resolve-through-the-stored-id) because the
two failure directions are asymmetric: feeding the stored id into resolution would make
the stored value *causal* on the computation — the precise defect class the operator
directive forbids — whereas comparing it against the resolver's answer makes the law
causal and the stored value a checked claim. The structural property that `revision_id`
narrowing cannot divert within a valid registry means the cheapest correct
implementation of the creation gate is the resolver itself; the calc-time assertion
then covers the only remaining divergence vector (post-creation registry corrections
and pre-gate legacy units), which a creation gate alone can never catch.

R2 is decided YES because the carry path is the one place where a revision error
*compounds across years*: a prior observation filed under the wrong revision injects
that revision's norms into every later filing that folds it in. Today the persisted
envelope cannot even express the question — there is no revision field — so the gate
necessarily comes with the provenance stamp. The blocking/advisory split follows the
no-silent-under-declaration discipline: a *contradicted* claim blocks; an *absent*
claim (legacy data) warns loudly but does not brick years of stored history.

D3 is decided FULL because an unauditable legal anchor under a "law-determined"
resolver is structurally identical to the Modelo 200 DT-44ª incident that produced the
registry-calculation-legal-grounding rule: a value (here, an applicability window) with
no binding-provision citation has no anchor to verify against and drifts undetected.
The cost is modest — the ordenes are already cited in `legal_refs` for the audited
examples, so the field largely promotes existing data to structure — and the payoff is
that "revision X is legally correct for year Y" becomes a mechanical registry-gate
check instead of an archaeology exercise.

## Consequences

- **Gains.** The period→revision binding becomes an enforced, auditable invariant
  end-to-end: declared in TOML, proved unambiguous at registry load, resolved by one
  function, asserted at work-unit creation, re-asserted at calculation, re-confirmed at
  cross-year carry, and anchored to BOE through a validated orden field. The
  `--revision` flag stops being a foot-gun. A registry correction that changes the
  law-mapping surfaces as loud refusals on stale units instead of silent recomputation
  under a different revision than the unit's identity claims.
- **Costs and difficulties.** The calc-time assertion will refuse previously-working
  stale units after registry corrections — that is the point, but it is new operator
  friction and needs an instructive message plus a documented re-create path. The
  observation-envelope stamp is a persisted-schema addition behind an encrypted
  boundary: it needs the standard strict roundtrip + anti-tautology tests
  (roundtrip-discipline rule) and a deliberate legacy-read story. The D3 backfill
  touches every modelo's `revision.toml` and the legal catalogue; for some modelos the
  correct orden must be researched against BOE before it can be declared — the gate
  must not tempt anyone into decorative citations (the legal-grounding rule's
  corpus-text cross-check is the defence).
- **Pitfalls.** The advisory path for unstamped legacy observations must not become
  permanent camouflage; the plan should pair it with a backfill-or-ratchet so the
  advisory population shrinks monotonically. The contextless schema-browse fallback in
  `filing/runtime.py` remains a named exemption — it must never grow into a calc-path
  precedent for passing revision ids.
- **Pathways opened.** With the orden first-class, a future registry gate can verify
  applicability windows directly against the orden's corpus text (window-matches-law),
  and operator surfaces can answer "why this revision?" with a BOE citation instead of
  a directory name.

## Codification candidates



- **Rule slug:** `revision-resolution-is-law-determined`.
  **Rule:** Every production calculation, verification, filing, or export path resolves
  its registry revision from `(modelo, filing_year, period)` through
  `ValidatedRegistryAuthority` / `select_revision`; a stored, literal, or
  operator-supplied `revision_id` may only be *asserted equal* to that resolution
  (refusing instructively on divergence), never injected as the selector.

- **Rule slug:** `carried-observations-stamp-their-revision`.
  **Rule:** Every persisted prior-filing observation records the registry revision it
  was captured under, and every cross-period/cross-year carry re-confirms that stamp
  against `select_revision` for the source context before trusting the value — a
  divergent stamp blocks the carry, a missing legacy stamp surfaces a non-blocking
  advisory, never silence.
