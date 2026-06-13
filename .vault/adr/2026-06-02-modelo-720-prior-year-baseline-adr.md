---
tags:
  - '#adr'
  - '#modelo-720-prior-year-baseline'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-720-prior-year-baseline-research]]"
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
---



# `modelo-720-prior-year-baseline` adr: `modelo 720 prior-year asset baseline and re-declaration trigger` | (**status:** `accepted`)

## Problem Statement

The foundational multi-year-renta authorization gate requires every one of the 30
modelos to enroll via an end-to-end test that drives real backends across at least
two distinct renta years. Modelo 720 (declaración informativa de bienes y derechos
situados en el extranjero) is an informativa with no numeric calculation engine, so
its two-year evidence cannot be a calculation. The gate's foundational ADR places
720 in the THRESHOLD/CONTINUITY-CROSS-RENTA class, explicitly naming "the +€20.000
prior-year baseline" as its cross-year behaviour, and defers the per-mechanism
governance to a separate co-backing ADR. This is that ADR.

The architectural question is narrow: **what is the lowest-risk registry mechanism
that makes 720's prior-year asset baseline a real, resolvable cross-year dependency,
and surfaces the statutory re-declaration obligation without silently passing a filer
who under-declares a grown asset category?** The answer must (a) exercise two
distinct renta years so 720 can enroll, (b) preserve regulatory grounding end to end,
and (c) never block a legally correct filing.

The statutory substance: once a category of foreign asset has been declared, it must
be re-declared in a later year only if its joint valuation grew by more than €20.000
over the last-declared baseline (RD 1065/2007 arts. 42-bis.5 / 42-ter.5 / 54-bis.7).
A filer who lets a category grow > €20.000 and then omits it from the current filing
is under-declaring. The current 720 surface has no prior-year baseline to compare
against, so it cannot detect this — the silent-under-declaration hazard the
`no-silent-under-declaration` discipline exists to close.

## Considerations

- **The asset categories are a closed legal set.** Arts. 42-bis / 42-ter / 54-bis
  enumerate cuentas / valores / inmuebles. Because the set is closed and fixed, the
  baseline does not need a dynamic per-class grouping; a small fixed number of
  per-category bindings covers it.
- **The fichero already anticipates prior-year chaining.** `type_1` carries
  `numero-identificativo-de-la-declaracion-anterior` (offset 123–135) and
  `declaracion-complementaria-o-sustitutiva` (121–122); `type_1` carries the
  declaration-level `suma-total-de-valoracion-1` (145–162); `type_2` carries the
  per-record `clave-tipo-de-bien-o-derecho` (offset 102) and `valoracion-1` (432–446).
  No fichero format change is needed.
- **`filing_year_delta = -1` is the established prior-year hook.** The previous-filing
  resolver computes `expected_year = filing_year + filing_year_delta + period_year_delta`,
  so a `-1` delta resolves last year's filing. The Modelo 130
  `_previous_year_net_income_binding` is the canonical prior-year copy precedent, and
  `filing_year_delta = -1` is already exercised in the selector-shape tests.
- **The €50.000 initial threshold is already centralised** as
  `MODELO_720_REPORTING_THRESHOLD_EUR` in `src/aeat/core/external_constants.py`. The
  €20.000 re-declaration increment is **not** yet a constant and must be added beside it.
- **The re-declaration trigger is a genuinely new semantic.** No existing verification
  predicate operator expresses "current per-category total minus prior-year per-category
  baseline exceeds a fixed euro threshold, advisory when the grown category is absent".
  The closed operator set is `{advisory_when_ratio_ge, all_nonzero, any_nonzero,
  cap_le_when_positive, implies_nonzero, profile_field_required}`.
- **The M200 advisory is the precedent for the finding shape, not the evaluator.**
  M200 uses `implies_nonzero(["00501", "DP200014:00552"])` with
  `finding_kind = "ADVISORY"` to surface a single-filing under-declaration without
  blocking. The 720 trigger borrows the ADVISORY posture but needs a cross-year delta
  the M200 operator cannot express.

## Constraints

- **No schema change is permitted for the baseline path.** Verification against
  `_PreviousModeloSelector` (`extra="forbid"`) showed it declares no `grouping` key,
  and `RowSetGroupingKind` declares no per-foreign-asset-class member. The scratch
  design's `grouping = "per_foreign_asset_class"` is therefore not constructable. The
  baseline must use the singular `source_output` + `op = "copy"` shape with
  `period = "0A"` and `filing_year_delta = -1`. This is a hard constraint that the
  recommended cheap path already satisfies; the dynamic-grouping alternative is rejected
  as un-buildable, not merely more expensive.
- **The re-declaration evaluator is the one open design point.** Because no existing
  operator expresses the prior-year-baseline delta, the mechanism needs either one new
  ADVISORY predicate operator or a derived-casilla formulation gated by an existing
  operator. Either path must register the operator in
  `KNOWN_VERIFICATION_PREDICATE_OPERATORS` (or the formula registry) so a typo cannot
  silently pass the gate — the silent-pass hazard that constant already guards.
- **The trigger MUST stay ADVISORY.** Growth ≤ €20.000 legitimately need not be
  re-declared, and a category can legitimately drop below threshold. A BLOCKING_RULE
  would refuse legal filings. The advisory fires only on the suspicious shape
  (prior baseline present, growth > €20.000, category absent from current records).
- **Parent-feature stability.** This mechanism depends on (i) the previous-filing
  binding subsystem (mature: powers 390←303 and 130 carry-forward), (ii) the
  verification-predicate subsystem (mature: powers M200, M131, M210), and (iii) the
  authorization recorder's non-calculation two-year-context registration mode
  (introduced by the foundational gate ADR — this mechanism is a *consumer* of that
  mode and must not assume calculation-based capture). All three are stable enough to
  build on; the only new surface this ADR introduces is registry data plus one euro
  constant plus (at most) one advisory operator.

## Implementation

A registry-data-first mechanism in four small parts, none of which widens the schema.

**(1) Three fixed per-category baseline bindings.** Author three `previous_filing`
bindings — one each for cuentas, valores, inmuebles — in the 720 revision's bindings
tree. Each declares a distinct singular `source_output` naming that category's
prior-year per-class total, `filing_year_delta = -1`, `period = "0A"`,
`aggregation = { op = "copy" }`, and per-category `legal_refs`
(`rd-1065-2007:art-42-bis` for cuentas, `rd-1065-2007:art-42-ter` for valores,
`rd-1065-2007:art-54-bis` for inmuebles, each plus `ley-58-2003:da-18` and
`orden-hap-72-2013:art-2`). The closed-set fixedness is what lets three static
bindings replace a dynamic grouping. The copy-shape mirrors the verified
`modelo-390-prev-303-compensacion-ultimo-periodo` precedent.

**(2) The €20.000 re-declaration constant.** Add
`MODELO_720_REDECLARATION_DELTA_EUR = Decimal("20000.00")` to
`src/aeat/core/external_constants.py`, beside `MODELO_720_REPORTING_THRESHOLD_EUR`,
with a docstring citing arts. 42-bis.5 / 42-ter.5 / 54-bis.7. Centralising it keeps
the threshold out of test source (no hand-computed magic numbers) and gives the
threshold-logic oracle a single authoritative value to assert against.

**(3) The ADVISORY re-declaration trigger.** Per category, surface an ADVISORY finding
when the prior-year baseline binding resolved a non-zero value, the current-year
per-category total exceeds that baseline by more than
`MODELO_720_REDECLARATION_DELTA_EUR`, and the category is absent from the current
declaration's records. The decision between the two evaluator formulations is left to
the plan/reference, but the contract is fixed: ADVISORY only, grounded with
`legal_refs`, registered so the operator name cannot be a silent typo, and holding
trivially when the antecedent (prior baseline) is ≤ 0 so a first-time declaration
never trips it.

**(4) The two-year enrollment test.** A real-adapter test (no mocks) cloning the
`test_modelo_130_carry_forward_continuity.py` pattern — real SQLite, real
`ValidatedRegistryAuthority`, real previous-filing resolver — registers two distinct
renta years with the authorization recorder via its non-calculation two-year-context
mode. Scenario: Year N declares cuentas €60.000 and valores €55.000 (both > €50.000);
Year N+1 declares cuentas €85.000 (+€25.000 > €20.000 → re-declaration required) and
valores €65.000 (+€10.000 ≤ €20.000 → not required). The test asserts the three
baselines auto-resolve N→N+1, the advisory fires for cuentas and not for valores, and
the recorder observes two distinct years. The €20.000 / €50.000 thresholds are
statute-checkable, so the oracle is genuine threshold logic, not a tautological
structure check.

## Rationale

The cheap path (three fixed per-category bindings) is chosen because verification of
the live schema proved the dynamic per-class grouping is not merely costlier but
**not constructable**: `_PreviousModeloSelector` forbids extra keys and carries no
`grouping`, and `RowSetGroupingKind` has no per-class member. The closed legal set of
asset categories makes three static bindings a complete substitute, so the campaign
gets a real cross-year dependency with zero schema change — the lowest-risk possible
mechanism, which is why this ADR recommends it land first among the campaign's
mechanism ADRs.

The ADVISORY (not BLOCKING) posture follows `no-silent-under-declaration` and its
worked M200 precedent: the gate must make the under-declaration non-silent without
refusing the many legitimate zero-growth or below-threshold filings. The new
cross-year delta operator is accepted as necessary because the existing operators are
single-filing only; registering it in the known-operators set preserves the
silent-pass guard that protects every predicate. Centralising the €20.000 threshold
mirrors the existing `MODELO_720_REPORTING_THRESHOLD_EUR` and
`M347_THRESHOLD_EUR` constants, keeping `no-tautological-calculation-tests` satisfied:
the test asserts against the statutory constant, not against a number re-derived from
the formula under test.

The mechanism preserves regulatory grounding end to end (every binding and the
advisory carry `legal_refs` traceable to the reviewed corpus) and consumes only mature
parent subsystems plus the foundational gate's non-calculation recorder mode.

## Consequences

- **720 gains a real cross-year dependency and can enroll.** The three baselines plus
  the advisory give the informativa genuine two-year behaviour, lifting it from
  "structure-only" to a statute-grounded oracle — the strongest oracle in the
  informativa set.
- **A silent under-declaration hazard is closed.** A filer who lets a category grow
  > €20.000 and omits it now gets an operator-facing advisory rather than a silent pass.
- **One new euro constant and (at most) one new advisory operator.** Small, contained
  additions. The operator must be registered against the silent-pass guard; forgetting
  to register it is the main pitfall, and the existing known-operators gate test
  catches it.
- **No schema change, no fichero change, no engine build.** This is the cheapest
  mechanism in the campaign — pure registry authoring plus a constant plus an advisory.
  It de-risks the mechanism track and is recommended to land first.
- **Dependency on the foundational recorder's non-calculation mode.** 720 cannot enroll
  until that mode exists; this ADR does not build it, it consumes it. If the foundational
  gate slips its non-calculation registration mode, 720's enrollment slips with it.
- **The advisory's correctness hinges on the absent-category detection.** The trigger
  must distinguish "category grew > €20.000 and is absent" from "category legitimately
  dropped or stayed flat". A naïve delta test that ignores presence would either
  false-positive on shrinking categories or miss the omission; the plan must test both
  the firing and the non-firing legs explicitly.

This ADR is a **mechanism ADR co-backing the multi-year-renta campaign plan**
alongside the foundational gate ADR. It owns 720's cross-year behaviour and nothing
more; the authorization spine, recorder, and meta-test belong to the foundational ADR.

## Codification candidates

- **Rule slug:** `closed-legal-set-prefers-fixed-bindings-over-dynamic-grouping`.
  **Rule:** When a cross-year or aggregate dependency ranges over a closed,
  statutorily-fixed set of categories (e.g. the 720 foreign-asset classes), author one
  fixed binding per category rather than a dynamic grouping kind — especially where the
  previous-filing selector forbids a `grouping` key and no matching
  `RowSetGroupingKind` member exists.

  This candidate is a *narrowing* of the existing `no-silent-under-declaration` and
  registry-authority disciplines rather than a wholly new constraint; promote it only
  if the cheap-path-over-grouping decision recurs in the A2 / A4 mechanisms, otherwise
  leave it as documented rationale here.
