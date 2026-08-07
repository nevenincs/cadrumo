---
tags:
  - '#adr'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2b6c6f49c68809ec4741e8d2c3f13c4e18bd80cf1455921dab1f5e6f388dfc11'
related:
  - "[[2026-08-07-calculation-chain-integrity-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
  - "[[2026-08-07-silent-zero-regression-screen-research]]"
---

# `calculation-chain-integrity` adr: `Remediation shape for the silent-zero and silent-overclaim class` | (**status:** `accepted`)

## Problem Statement

The calculation engine screens one direction of silent under-declaration -- an observation nothing consumes -- and not its mirror: a binding that used to resolve a non-zero value now resolving zero, measured live on the M130 retenciones binding (`2026-08-07-silent-zero-regression-screen-research`). Three mechanisms sit adjacent to that gap and each misses it for a different reason, per that research. A decision on which detection mechanism ships must precede building anything (per this plan's Wave `W02` gate).

Direct prior art exists and narrows the decision more than the research alone shows. `2026-05-26-modelo-130-relation-regression-adr` (accepted) already solved the identical failure class for OBSERVATION-BACKED binding sources: `previous_filing` and `relation_prefill` bindings resolve through a three-state contract (resolved / absent-by-design / missing-error), enforced by the named `_OBSERVATION_BACKED_SLOT_SOURCES` constant, so a dead or malformed binding for those two source kinds raises loudly instead of silently zero-filling. That ADR's own final amendment states the scope explicitly: "Bound casillas with a non-observation-backed source (`profile`, `ledger_*`, invoice, withholding, etc.) continue to support the `inputs` projection fallback unchanged." The M130 retenciones binding measured in this plan's research is a **ledger-backed** binding -- explicitly the class that ADR's amendment left outside the three-state contract. The gap this ADR closes is therefore not a new problem; it is the known, already-named residual scope of an accepted sibling decision.

## Considerations

- Three existing mechanisms each miss the measured gap for a different reason (`2026-08-07-silent-zero-regression-screen-research`, Findings §1): the observation-consumption screen asks the wrong question; `expected_but_missing_binding_ids` asks the right family of question at the wrong granularity (`binding.id in resolved_binding_values` is `True` at either `300.00` or `0`); `implies_nonzero` is the right shape but verify-time and opt-in, never authored for this casilla.
- The observation-backed three-state contract (`2026-05-26-modelo-130-relation-regression-adr`, Decision 2 / the observation-backed-scope amendment) is direct, already-shipped prior art for exactly this failure class, scoped narrower than this decision needs (two source kinds, not the ledger-backed and other non-observation-backed sources this gap covers).
- The relation-prefill tier's own contract (`src/cadrumo/application/calculations/_relation_prefill.py`) establishes the authoritative shape of "legitimately empty": no prior filing for a relation returns `value=None`, `provenance="operator_manual"` -- a blank the operator fills by hand, never a zero the engine asserts. Any detection mechanism must treat this as the false-positive floor, not a defect signature.
- False-fire cost is the dominant selection criterion. The project has already paid for an advisory that fires on legitimately-exempt cases once this session (`ledger-iva-advisory-only-on-cuota-bearing-categories`); a detector whose false-fire rate tracks normal business or first-filing variation will be dismissed within a session or two and then protects nothing while appearing to.
- `no-tautological-calculation-tests` and `no-silent-under-declaration` both bear on any chosen mechanism's own test/grounding shape.

## Considered options

1. **Calculate-time comparison against the prior period/revision.** Catches the measured regression directly. Rejected: no generic prior-revision-load primitive exists today (`previous_filing` binding resolution is source-specific, not a general diff primitive), and the false-fire risk is structural, not incidental -- a taxpayer legitimately has zero retenciones after a nonzero prior quarter routinely (a client stopped paying, a contract ended), and the relation-prefill tier's own no-prior-filing-is-legitimately-blank contract confirms the same shape recurs on first filings. Also structurally blind to a wrong-but-nonzero regression.
2. **Registry-build reachability.** Asserts every declared ledger-backed binding can match at least one constructible observation shape, at build time, with no runtime taxpayer state. Catches the measured failure directly and before any run. Cannot catch a binding that reaches real rows and aggregates them wrong. Cost is real but scoped per binding-source family, hung on the existing per-family module seam (`registry-resolver-family-extraction`).
3. **Golden-value regression (pinned, grounded fixture).** Catches only the fixtured scenarios; coverage scales with authored fixtures, not the registry's real surface. Rejected as the primary mechanism for that reason; viable as supplementary coverage once a primary mechanism exists.
4. **Extend the existing observation-backed three-state contract to a build-time-enforced floor covering ledger-backed (and other non-observation-backed) sources.** Not a new mechanism -- generalises `2026-05-26-modelo-130-relation-regression-adr`'s already-shipped shape (resolved / absent-by-design / missing-error) beyond its current two source kinds, layered with the existing `implies_nonzero` verification-predicate mechanism (`application/modelo/_verification_predicates.py`) made mandatory rather than opt-in for casillas in scope. Lower cost than option 2 alone (reuses shipped infrastructure); weaker alone (depends on an author's antecedent choice being sound).

## Constraints

- No mocks, fakes, stubs, monkeypatches, skips, xfails, or tautological assertions (`aeat-quality-gates`, `no-tautological-calculation-tests`). The mutation proof for any built gate must physically break a real binding's reachability and observe the gate redden.
- No shims, no parallel silent-zero-tolerant paths introduced alongside the new gate (`no-legacy-compatibility`, `aeat-architecture-boundaries`).
- The gate must not fire on either established legitimate-zero shape: a genuinely absent-by-design observation-backed slot (already covered by the 2026-05-26 ADR's contract) or a relation-prefill tier's no-prior-filing blank (`_relation_prefill.py`).
- Per-family reachability probes are scoped work, not one universal function -- each binding source family already declares a typed selector (`BindingSourceKind` plus its per-family selector model, `binding-validation-single-contract`), so each family's probe is independently authored and independently testable.

## Implementation

Two additive layers, neither replacing the other:

**Primary -- registry-build reachability (option 2).** For each ledger-backed (and other non-observation-backed) binding source family, a build-time probe constructs a synthetic minimal matching row from the family's own declared selector shape and asserts the resolver accepts it as a candidate. A binding whose selector cannot match any constructible shape fails registry build, naming the binding and the family. This generalises the same structural principle `2026-05-26-modelo-130-relation-regression-adr`'s Decision 1 (`max_year_delta` anchor-dropping) already applies to the observation-backed selector shape: a binding's absence-or-presence is a property the selector declares, not a runtime accident.

**Layered -- the `implies_nonzero` coverage floor (option 4).** Registry build additionally asserts that every casilla whose binding source is ledger-backed either names a `verification_predicate` in which it appears as a consequent, or is listed on an explicit, named, reasoned can-legitimately-be-zero exemption set -- mirroring `CUOTA_LESS_M303_IVA_CATEGORIES` (`src/cadrumo/domain/iva/_schema.py`), the project's own established pattern for a reasoned zero-is-fine carve-out. This closes the residual gap option 2 cannot reach on its own: a resolver correctly wired to real matching rows that aggregates them incorrectly still has SOME declared antecedent-nonzero check watching it, even though that check's strength depends on the authored predicate.

**Rejected -- calculate-time prior-period comparison (option 1).** Not built. The false-fire profile is structural (routine business variation, first-filing blanks already contracted as legitimate by the relation-prefill tier) rather than a tuning problem, and no state-loading primitive exists to build it on cheaply.

Every built probe/predicate ships with a mutation proof (plant a binding retargeted to match nothing; confirm the gate reddens naming it; revert; confirm green) and states in its own docstring what it cannot catch -- the wrong-but-nonzero aggregation case remains outside both layers and is named as a residual limit, not implied covered.

## Rationale

Options 2 and 4 win because they are the only pairing with LOW false-fire risk by construction: both run against the registry's own declared shape (option 2) or a declared antecedent (option 4) rather than against a taxpayer's actual filing data, so neither can fire on a legitimately-zero real filing. Option 1 is rejected on the single criterion this project has already paid to learn the hard way this session: an advisory whose false-fire rate tracks normal variation gets dismissed and then protects nothing while appearing to. Option 3 is kept as future supplementary coverage, not the primary mechanism, because its coverage scales with authored fixtures rather than the registry's real binding surface. Choosing option 4 as a genuine generalisation of `2026-05-26-modelo-130-relation-regression-adr`'s shipped contract -- rather than a fresh, unrelated mechanism -- means the project ends this decision with ONE conceptual model for "is this binding's zero legitimate" (resolved / absent-by-design / missing-error) applied consistently across every binding source kind, not two different apparatuses solving the same problem for different source families.

## Consequences

Gain: the silent-zero class this session measured on M130 retenciones becomes structurally impossible for any ledger-backed binding whose selector genuinely cannot match anything, and every ledger-backed casilla gains an explicit, auditable statement of what nonzero antecedent it depends on (or why it may legitimately be zero). The three-state contract becomes the ONE model spanning observation-backed and ledger-backed sources, closing the scope gap `2026-05-26-modelo-130-relation-regression-adr`'s own amendment named but did not close.

Honest difficulties. The per-family reachability probes are real, scoped authoring work across 7+ source kinds (`2026-06-10-calculation-engine-foundations-audit`, finding F4's enrolled-source estimate) -- this is a campaign, not a single commit, and `W02.P03` (building the gate) is explicitly gated on this ADR's acceptance rather than started alongside it. The `implies_nonzero` floor's safety depends on predicate-authoring discipline: a technically-true but weak antecedent satisfies the build-time floor while protecting little, so a reviewing eye on each authored predicate remains necessary and is not itself automated away by this decision.

Pathway opened: once both layers exist, the wrong-but-nonzero residual (a correctly-wired binding that aggregates real rows incorrectly) becomes the next-named gap for a future decision, rather than an unstated one.
