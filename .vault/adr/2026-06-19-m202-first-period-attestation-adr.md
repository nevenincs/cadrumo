---
tags:
  - '#adr'
  - '#m202-first-period-attestation'
date: '2026-06-19'
modified: '2026-06-19'
related:
  - '[[2026-06-13-first-filer-attestation-adr]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
  - '[[2026-06-05-cross-period-calculation-guards-adr]]'
---

# `m202-first-period-attestation` adr: `scope out first-year modalidad-cuota Modelo 202 obligation via grounded attestation` | (**status:** `accepted`)

## Problem Statement

A genuinely-not-obligated first-year Impuesto sobre Sociedades (IS) company
cannot clear the Modelo 200 to Modelo 202 cross-period clean-state gate. The gate
(`src/aeat/application/calculations/_cross_period_clean_state.py`) derives a
cross-period dependency on Modelo 202 (pagos fraccionados) and demands AEAT
evidence of a prior-period Modelo 200/202 filing. For a first-year IS filer under
modalidad cuota (LIS art. 40.2) that evidence cannot exist: in modalidad cuota the
pago fraccionado is a percentage of the cuota integra of the LAST IS return whose
filing deadline has elapsed, and a company in its first IS year has no such prior
return — so no pago fraccionado is owed and no prior Modelo 202 was ever filed.
The gate blocks verify and export demanding evidence of a filing the law never
required, with no legitimate offline exit.

The sibling first-filer attestation work
(`2026-06-13-first-filer-attestation-adr`) does not cover this case. Its
pre-activity suppression is keyed on a STRICTLY-prior CALENDAR span
(`period.end_date < activity_start_date`) and is guarded by
`Period.has_date_span()`. The Modelo 202 instalment periods (`1P` / `2P` / `3P`)
have no calendar span, so the pre-activity predicate returns `False` for them and
never suppresses them. A distinct, modality-and-first-year-keyed suppression is
required.

## Considerations

The legal reality is the foundation. LIS art. 40.2 (modalidad cuota): the pago
fraccionado is computed on the cuota integra of the last IS return whose deadline
has elapsed; absent a prior IS return there is no basis and no obligation. LIS
art. 40.3 (modalidad base imponible, mandatory when the importe neto de la cifra
de negocios — INCN — of the prior 12 months exceeds 6.000.000 euros): the pago
fraccionado is computed on the CURRENT year's running base imponible, so it IS
owed in the first IS year. The split therefore hinges on the derived modality.

The obligation logic already exists and is grounded:
`derive_modelo_202_modality(profile)` in
`src/aeat/domain/calculations/registry/_applicability_modelo202.py` returns
`ART_40_2_OPTIONAL` (legal entity, INCN <= 6.000.000), `ART_40_3_MANDATORY`
(legal entity, INCN > 6.000.000), or `INCOMPLETE` (not a legal entity, or INCN
undeclared). The first-year fact is read from the operator-declared
`activity_start_date` already carried on the profile and already trusted by the
deadline engine and the first-filer attestation gate.

## Constraints

This decision amends an accepted safety gate and must thread two sibling ADRs
without weakening them:

- `2026-06-05-cross-period-filing-clean-state-adr` (accepted) introduced the gate
  and assumes every cross-period dependency is a real prior obligation. This ADR
  scopes out ONLY the Modelo 202 dependency, and only under the narrow
  first-year-modalidad-cuota condition; every other dependency and every other
  modality stays in scope and keeps blocking (fail-closed).
- `2026-06-05-cross-period-calculation-guards-adr` (accepted) mandates the
  requirement graph be registry-derived and forbids a caller-invented ad hoc
  dependency shrink. The narrowing here is driven by a GROUNDED, derived input —
  the Modelo 202 modality derived from the profile's declared INCN plus the
  declared `activity_start_date` — not a per-call parameter a caller invents. The
  registry-derived requirement graph is unchanged; the suppression is an
  application-layer filter over it, exactly as the first-filer attestation
  pre-activity suppression is.

## Implementation

Add a new typed provenance facet
`NoPriorObligationProvenanceKind.NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR`,
docstring-grounded in LIS art. 40.2, distinct from the pre-activity facet.

Disambiguate the evidence properties on `CrossPeriodDependencyEvidence`:
`suppressed_pre_activity` is narrowed to check the pre-activity facet
specifically; a new `suppressed_first_year_fractional` checks the new facet;
`operator_declared_suppression_advisory` is scoped to the pre-activity facet only
so the two suppressions' advisories never cross-fire.

A new evidence builder `_suppressed_first_year_fractional_evidence` mirrors the
pre-activity builder but stamps the new facet kind; the provenance kind stays
`OPERATOR_DECLARED` because the determination rests on operator-declared inputs
(INCN-driven modality plus declared activity-start), carrying the
operator-declared advisory rather than a silent omission.

The evaluator `evaluate_cross_period_clean_state` gains a keyword
`modelo_202_modality: Modelo202Modality | None = None` (default `None` preserves
current behaviour). After the existing activity-start partition, among the
in-scope requirements it splits out those that qualify for first-year fractional
suppression. A requirement qualifies IFF: its source modelo is `202`, the derived
modality is `ART_40_2_OPTIONAL`, an `activity_start_date` is recorded, AND that
date's year is on or after the target filing year (the first IS year, no prior IS
basis). Qualifying requirements produce a clean facet-stamped evidence row;
everything else is evaluated normally. Suppression is REFUSED — the dependency
stays in scope and keeps blocking — when the modality is `ART_40_3_MANDATORY`,
`INCOMPLETE`, or `None`, when no activity-start date is recorded, or when the year
is not the first IS year.

Two verdict properties expose the outcome:
`suppressed_first_year_fractional_dependencies` and
`has_first_year_fractional_suppression_advisory`.

At the verification, export, and filing call sites (one-path parity), each derives
`derive_modelo_202_modality(workflow_profile).modality` and threads it through
`_require_cross_period_clean_state` / the verdict builder. When the verdict carries
`has_first_year_fractional_suppression_advisory`, a NON-BLOCKING advisory finding
is emitted (mirroring the pre-activity operator-declared advisory) naming the
assumption: a first-year entity under modalidad cuota (LIS art. 40.2) has no
Modelo 202 obligation, and if the entity elected modalidad base (art. 40.3) it IS
obligated and must file Modelo 202 — the operator bears legal responsibility. The
advisory is `legal_refs`-grounded in LIS art. 40.

## Rationale

The suppression is grounded in legal reality (no art. 40.2 pago fraccionado
without a prior IS return) and keyed on already-trusted, derived inputs rather
than a caller-invented narrowing. It is the Modelo-202-specific complement to the
first-filer attestation pre-activity scoping: that gate handles calendar-span
prior periods; this one handles the no-calendar-span instalment dependency that
the pre-activity predicate structurally cannot reach. Reusing the existing
no-prior-obligation evidence vocabulary (a typed provenance facet plus a
provenance-marked clean row) keeps the surface auditable and non-silent, and
threads the existing advisory mechanism rather than inventing a parallel one.

## Consequences

A genuinely-not-obligated first-year modalidad-cuota IS company gains a legitimate
offline path: verify completes on the merits of the current period, and export and
file open transitively. Every official-evidence gate is untouched; the fix removes
a demand for evidence of a filing the law never required.

### Abuse analysis — does this weaken the first-filer attestation mitigation?

No. The accepted `2026-06-13-first-filer-attestation-adr` rests its
dishonesty-resistance on the principle that "an operator cannot scope away an
obligation that fell after the claimed start" — a real filing that post-dates the
claimed alta is still in scope and still demands official evidence. This decision
does not weaken that principle; it is a distinct, narrower, fail-closed
suppression with its own independent grounding:

- It is keyed on a DERIVED modality, not on a free operator claim. The modality is
  derived from the declared INCN through the existing
  `derive_modelo_202_modality`. To obtain the suppression the entity must be a
  legal entity with INCN <= 6.000.000 euros — and an INCN above the threshold
  flips the modality to `ART_40_3_MANDATORY`, which is REFUSED suppression and
  keeps blocking. An operator cannot scope away a mandatory-modality obligation by
  declaration.
- It is fail-closed for every non-qualifying case: `ART_40_3_MANDATORY`,
  `INCOMPLETE` (not a legal entity / INCN undeclared), and `None` modality all
  keep the Modelo 202 dependency in scope and blocking. A missing modality is
  never read as "no obligation".
- It only suppresses the FIRST IS year (`activity_start_date.year >=
  target_filing_year`). A later year, or a prior IS return that genuinely exists,
  is on or after the basis and stays in scope — mirroring the first-filer
  principle that an obligation falling after the claimed start is still demanded.
  An operator who claims a later first-year than reality would still face the
  in-scope evidence demand for any real prior obligation.
- The suppression is surfaced NON-SILENTLY: a typed `OPERATOR_DECLARED` provenance
  facet plus a non-blocking, `legal_refs`-grounded advisory naming the
  modalidad-base (art. 40.3) responsibility. The determination is never presented
  as AEAT-authoritative and is visible to any reviewer or audit consumer
  (`no-silent-under-declaration`).

The new facet is also kept strictly distinct from the pre-activity facet so the
two suppressions and their advisories never cross-fire, preserving the
first-filer gate's behaviour unchanged.

### Costs

The gate gains a dependency on the derived Modelo 202 modality at the three call
sites; the derivation is pure over the profile and already exists. The provenance
surface gains one typed facet that downstream consumers (audit, overview) may want
to render.

### Rule-compatibility notes

- `no-silent-under-declaration`: satisfied. The suppression is a typed,
  advisory-surfaced outcome, not a silent blank.
- `aeat-safety-legal-gates`: satisfied and honestly bounded. The determination is
  grounded in LIS art. 40.2/40.3 and in derived modality plus the same declared
  field the deadline engine trusts; it claims operator-declared (not AEAT-sourced)
  provenance and surfaces an advisory. No live AEAT write is introduced.
- `local-filed-observations-are-non-official-evidence`: satisfied and unchanged.
  `_OFFICIAL_SOURCE_KINDS` and the `app_filing` kind are untouched.

## Codification candidates

- **Rule slug:** `m202-first-year-modalidad-cuota-suppression-is-modality-keyed`.
  **Rule:** A Modelo 202 cross-period dependency may be scoped out as a first-year
  no-fractional-payment obligation only when the DERIVED Modelo 202 modality is
  `ART_40_2_OPTIONAL` and the recorded activity-start year is at or after the
  target filing year; it is fail-closed (kept in scope, blocking) for
  `ART_40_3_MANDATORY`, `INCOMPLETE`, or unknown modality, and the suppression is
  stamped with a distinct typed provenance facet plus a non-blocking advisory.
  (Promote only after this ADR holds across a full execution cycle.)
