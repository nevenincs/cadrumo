---
tags:
  - '#adr'
  - '#live-parity-oracle'
date: '2026-05-08'
modified: '2026-07-17'
related:
  - "[[2026-05-06-live-parity-oracle-backend-research]]"
  - "[[2026-05-07-live-parity-oracle-adr]]"
  - "[[2026-05-07-aeat-vies-surface-split-ixvi-vs-groi-adr]]"
  - "[[2026-05-07-live-parity-oracle-plan]]"
  - "[[2026-05-07-live-parity-oracle-reference]]"
---

# `live-parity-oracle` ADR: cross-reference applicability gate | (**status:** `accepted`)

## Context

The live-parity oracle backend treats every cross-reference as
unconditionally applicable once its parent modelo's filing schedule
is in scope. This was acceptable while the only registered
cross-references were universally relevant (record-design parity,
NIF-IVA verification, calc-portal access). The arrival of GROI as
the first authenticated_simulator binding broke that assumption: not
every taxpayer who files Modelo 349 needs the GROI Spanish-ROI
counterparty consult, and a taxpayer who isn't ROI-enrolled has no
business invoking the surface at all.

ROI enrollment is governed by the Modelo 036 / 037 census procedure
(checkbox 582 in the standard 036 template). It is an opt-in legal
state distinct from the operational fact captured by the existing
`iva.does_intracomunitario` profile field. Two separate axes:
- "Do you currently conduct intracommunity operations?" (operational)
- "Are you registered on the ROI / VIES registry?" (census state)

A taxpayer can be operationally intracom-active without yet having
opted into ROI (the inverse legal-but-not-operational state is also
possible). The applicability gate must accommodate both axes
independently so future bindings can declare whichever predicate
they need.

## Decision

Extend `LiveCrossReferenceDecision` with two optional fields:

- `applicability_predicates: tuple[ProfilePredicateDefinition, ...]`
- `applicability_condition_mode: Literal["all", "any"] = "all"`

An empty predicate tuple means "unconditionally applicable" as a current
schema semantic. It is not a migration alias: every registry binding is
validated directly against the one current shape.

Add a typed pydantic-strict result `CrossReferenceApplicability`:
fields `cross_reference_id`, `applicable: bool`,
`matched_explanations`, `unmet_predicate_fields`.

Add `evaluate_cross_reference_applicability(decision, profile_facts)`
to `_live_parity.py` as the single canonical evaluator. It reuses
`profile_condition_matches` from `_schedules.py` rather than
duplicating predicate-resolution logic.

Add a new `iva.roi_enrolled` boolean profile field to the user
profile schema so applicability predicates can reference it. The
field's description explicitly distinguishes ROI enrollment from
the operational `iva.does_intracomunitario`.

Bind an applicability predicate requiring
`does_intracomunitario == true` to the GROI cross-reference on
Modelo 349.

## Rationale

Profile-state predicate evaluation already exists for filing
schedules. Mirroring that pattern onto cross-references keeps a
single semantic vocabulary across the registry; agents who learn
the schedule predicate model can read the cross-reference predicate
model without retraining. The schema validator's any-mode + empty
rule transfers directly.

A typed `CrossReferenceApplicability` rather than a bare bool:
- Surfaces matched_explanations for audit and UX (why a binding
  fired, what the user has to confirm).
- Surfaces unmet_predicate_fields so live tests and the resolver can
  produce a precise diagnostic.
- Aligns with the project pydantic mandate (every boundary record
  is pydantic v2 strict frozen).

The empty-predicates rule gives universal bindings an explicit canonical
representation. IXVI, OSS, and future optional bindings declare their own
source-grounded predicates directly; no alternate legacy representation is
accepted.

## Alternatives considered

- Resolver-side filter on profile facts only: rejected because it
  places the applicability rule outside the registry's declarative
  truth, breaking the audit story.
- Synthesise applicability from `requires_authentication` + other
  schema fields: rejected because authentication and applicability
  are orthogonal axes (an authenticated read of the user's own
  filings is universally applicable; GROI is auth-gated AND profile-
  gated).
- Add applicability as a calculated property on
  `ConstructDefinition` rather than per cross-reference: rejected
  because constructs aggregate cross-references that may carry
  different applicability profiles (a 349-informative construct
  can host both an always-on portal binding and an optional GROI
  binding).

## Consequences

Positive:
- Optional cross-references are declared explicitly with no adapter-
  side conditional logic.
- The audit-oracles JSON gains a typed signal for which bindings
  are profile-gated.
- Applicability-negative tests assert that the oracle is not invoked and that
  the typed reason identifies the unmet profile facts. Enabled live tests fail
  on real boundary errors; inapplicability is a domain result, not an ignored
  test outcome.

Negative:
- Each new predicate adds fixture surface. Mitigated by the
  pydantic profile model providing a single canonical fixture
  shape.
- Registry verify time grows linearly with predicate count (each
  predicate's legal_refs and source_refs are catalogue-checked).
  Negligible at current binding counts.

## Compliance

- No-tautology mandate: predicate evaluation is structural against
  profile state, not formula arithmetic.
- Pydantic mandate: `CrossReferenceApplicability` is pydantic v2
  strict frozen.
- Corpus byte-protection precedent: the prek hook excludes
  `corpus/` so the Modelo 036 ROI artefact captured under the
  follow-up corpus slice stays byte-exact.
