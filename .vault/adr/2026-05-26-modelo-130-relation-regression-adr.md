---
tags:
  - '#adr'
  - '#modelo-130-relation-regression'
date: '2026-05-26'
modified: '2026-06-29'
related:
  - "[[2026-05-19-modelo-130-relation-regression-research]]"
  - "[[2026-05-26-modelo-130-relation-regression-audit]]"
  - "[[2026-05-19-modelo-130-relation-regression-plan]]"
---

# `modelo-130-relation-regression` adr: `same-ejercicio-prior-period-selector-and-bound-casilla-zero-default-elimination` | (**status:** `accepted`)

## Problem Statement

The Modelo 130 prior-quarter negative-result carry-forward (casilla 15
mechanics from AEAT Modelo 130 instructions under the RD 439/2007 art. 110
payment framework) is structurally undeclarable in the current registry
runtime, and casillas whose declared bindings fail to resolve silently default
to `Decimal("0")` instead of surfacing the failure. Two coupled defects produce
one regression:

**Selector capability gap.** The `_PreviousModeloSelector` model
expresses two source-period shapes: explicit period anchors
(`period` / `source_periods`) and integer offsets
(`source_period_offset_from_target`). Neither models AEAT's
"trimestre anterior within the same ejercicio, suppressed for the
first period" rule. The integer-offset shape with `offset = -1`
applied to a 1T target produces (year_delta=-1, period="4T") — i.e.
4T of the prior **ejercicio**, which violates AEAT's casilla 15
instruction.

**Silent zero fallback for bound casillas.** `_initial_values` in
`src/aeat/domain/calculations/registry/_formula_runtime.py` treats
every non-computed casilla uniformly with
`inputs.get(casilla.id, _ZERO)`. A casilla whose `input_kind =
"bound"` and whose binding fails to resolve at runtime (because the
binding selector is malformed, classified as relation-driven with no
relation, or otherwise undeliverable) silently becomes
`Decimal("0")`. The runtime cannot distinguish between
"legitimately zero" and "binding-resolution failure masquerading as
zero". Tests written against the dead state pass; the regression
hides.

The combination produces the observed Modelo 130 behaviour: the
carry-forward binding declared at `modelo-130-resultados-negativos-anteriores`
is silently skipped by the resolver, casilla 15 becomes zero, the
diferencia (casilla 17) and resultado final (casilla 19) are
calculated as if no prior quarter ever ran negative, and no test
fires.

## Considerations

### Same-ejercicio prior-period selector — shape options

**Option A — extend `_PreviousModeloSelector` with a constrained
mode**. Add `source_period_offset_from_target_same_ejercicio: int |
None`. When set, the resolver computes the offset period and emits
an empty anchor tuple when the implied `period_year_delta` would be
non-zero. For 2T/3T/4T this resolves to (0, prior-period); for 1T
it resolves to an empty anchor tuple and the binding produces no
observation requirement and no value. Local change. Single new
field. The required-anchor return type already supports the
empty-tuple shape (`required_period_anchors_for_target` already
returns `()` when `_derive_offset_source_anchor` returns `None`).

**Option B — declare per-target-period `RelationDefinition`
records**. Modelo 130 grows a `[[revisions...relations]]` array with
one entry per (target_period, source_period) edge: (2T→1T),
(3T→2T), (4T→3T), no entry for 1T. The binding stays declared but
moves to the relation-driven branch and is resolved by the relation
system. This is the path the selector validator's mode (c)
(`source_output` without period anchor) already anticipates.

**Option C — extend `_PreviousModeloSelector` with a generic
`max_year_delta` cap on the integer-offset shape**. The offset
resolver still produces (year_delta, period) anchors, but anchors
whose `year_delta` exceeds `max_year_delta` (default 0 for
same-ejercicio) are dropped. Generalises beyond Modelo 130.

### Bound-casilla zero-default — elimination options

**Option Z1 — bound casillas require explicit binding values**.
`_initial_values` keeps the zero default for `manual` casillas but
NOT for `bound` casillas. Bound casillas with no resolved binding
value raise `RegistryValidationError` at the start of calculation
naming the dead binding. Manual inputs may still legitimately
default to zero (operator left the field blank).

**Option Z2 — every bound casilla resolves only via its binding,
never via `inputs`**. Reinforces Z1 by also rejecting `inputs` that
target a bound casilla (parallel to the existing rejection of
`inputs` targeting computed casillas). The test that masks the dead
state (`"15": Decimal("0")` in the inputs mapping) becomes
test-time error.

**Option Z3 — typed three-state binding value: "resolved",
"absent-by-design" (the binding declares first-period suppression
or analogous emptiness), "missing-error" (the binding should have
resolved but did not)**. The runtime distinguishes the three
states. Bound casillas with "absent-by-design" produce zero through
an explicit constructor (not a silent default). "missing-error"
raises.

## Constraints

- No mocks, fakes, stubs, monkeypatches, skips, xfails, or
  tautological assertions in production tests. The regression gate
  must be a real-behaviour test that calculates a 2T snapshot from
  a 1T observation and would fail today against the dead binding.
- No shims, no parallel chains, no deprecation paths. The dead-state
  binding declaration in `130.toml` is replaced by the correct one
  in the same commit that lands the selector capability.
- The legal grounding split for the carry-forward rule is current as of
  2026-06-29: `[legal."rd-439-2007:art-110"]` is reviewed and
  BOE-permalinked for the vigente payment framework, while the casilla 15
  negative-result mechanics are grounded in `aeat-modelo-130-instructions`.
  The current BOE consolidated art. 110 has no vigente apartado 5, so the
  remediation must not revive the retired art. 110.5 premise.
- Shared-worktree discipline. The fix touches
  `src/aeat/domain/calculations/registry/_bindings.py`,
  `_formula_runtime.py`, `_data/registry/aeat/modelos/130.toml`,
  and adds a new test file. Every touched file must be path-staged
  via `git commit -- <paths>`.
- ABSENT cases must be observable, not silent. A binding that
  cannot resolve must produce a failure unless its absence is
  declared by the binding itself (first-period suppression). Tests
  must be able to distinguish "casilla legitimately zero from
  manual input or computed formula" from "casilla zero because a
  binding silently died".
- Decimal("0") remains a valid CALCULATED output. A formula that
  evaluates `max(0, -C17)` and yields zero is correct. A formula
  that subtracts two equal values and yields zero is correct. The
  prohibition is on zero arriving via dead-binding fallback, not on
  zero arriving via legitimate arithmetic or legitimate manual
  input.

## Implementation

### Decision 1 — selector capability: adopt Option C (generic
`max_year_delta` cap)

`_PreviousModeloSelector` gains an optional
`max_year_delta: int | None` field. When set, the resolver
(`required_period_anchors_for_target` and the call sites in
`previous_filing_observation_requirements` /
`resolve_previous_filing_binding_values`) discards anchors whose
implied `period_year_delta` strictly exceeds `max_year_delta` (so
`max_year_delta = 0` admits same-year anchors and drops cross-year
anchors). The dropped-anchor case produces NO observation
requirement and NO binding value, surfacing as "absent-by-design"
to the runtime (see Decision 2).

The Modelo 130 binding becomes:

```
[[revisions."2019-y-siguientes".bindings]]
id = "modelo-130-resultados-negativos-anteriores"
source = "previous_filing"
selector = { source_modelo = "130", source_output = "saldo-negativo-fin-periodo", source_period_offset_from_target = -1, max_year_delta = 0 }
aggregation = { op = "copy" }
```

Option C is preferred over A and B because:
- Option A bakes the AEAT rule into a same-ejercicio-specific
  field; future modelos may need other year-cap shapes.
- Option B requires declaring per-period relations and grows the
  relation surface for a contract the existing offset shape almost
  models; the binding selector is already the natural home for
  period semantics.
- Option C is one field, generalises, and reuses the existing
  empty-anchor return path.

### Decision 2 — zero-default elimination: adopt Option Z2

`_initial_values` no longer defaults bound casillas to zero from
the `inputs` mapping. Concretely:

1. `inputs` targeting any casilla with `input_kind = "bound"`
   raises `RegistryValidationError` ("bound registry casillas
   cannot be supplied as inputs"), parallel to the existing
   computed-casilla rejection. This forces test fixtures and
   production callers to stop pretending bound casillas are
   operator-supplied.
2. Bound casillas resolve only via the binding pipeline:
   `resolve_previous_filing_binding_values` → consumed by the
   formula runtime via `binding_values`. The runtime stops looking
   in `inputs` for bound casillas.
3. A bound casilla whose binding is declared and is expected to
   produce a value (i.e. the selector resolved at least one anchor)
   but did not deliver one raises
   `RegistryValidationError("binding {id!r} expected one observed
   filing ...")` — this branch already exists in
   `resolve_previous_filing_binding_values` and is preserved.
4. A bound casilla whose binding declared NO anchors for the
   target period (e.g. first-period suppression via Decision 1) is
   marked "absent-by-design". The runtime materialises it as
   `Decimal("0")` through an explicit constructor path keyed off the
   selector's empty-anchor return, NOT through the `inputs.get(...,
   _ZERO)` fallback. The provenance carried by the
   `CasillaObservation` for that casilla records the
   absent-by-design state so audit trails can distinguish it from a
   value-bearing observation.

The fallback in `_initial_values` for `manual` casillas is
preserved unchanged. Operators leaving a manual field blank is a
legitimate operational shape and the existing test suite depends on
it.

### Decision 3 — regression gate: real-behaviour test in
`test_modelo_130_registry.py`

Add three tests:

1. `test_modelo_130_first_period_carry_forward_is_absent_by_design`
   — build a 1T snapshot, calculate with no previous-filing
   observations. Assert C15 = `Decimal("0")` AND assert the
   resulting `CasillaObservation` for C15 carries the
   absent-by-design provenance marker.
2. `test_modelo_130_second_period_carry_forward_picks_up_first_period_saldo`
   — build a 1T `RegistryModeloObservation` with casilla 17
   negative (so the seed `saldo-negativo-fin-periodo` is positive),
   resolve previous-filing bindings against a 2T snapshot, calculate
   2T, assert C15 = the 1T saldo seed, assert C17 reflects the
   subtraction, assert the C15 observation carries provenance
   pointing at the 1T source.
3. `test_modelo_130_bound_casilla_rejects_input_override` — call
   `calculate_registry_snapshot` with `inputs={"15":
   Decimal("100")}`. Assert `RegistryValidationError` is raised
   naming casilla 15 and the `input_kind = "bound"` rejection
   reason.

All three are real-behaviour: no mocks, no fakes, no
monkeypatches. Test 2 derives expected values from the
saldo-negativo seed formula's structural contract (copy of a
specific input), not from re-deriving the formula under test, so it
satisfies the no-tautological-calculation-tests rule.

### Decision 4 — legal grounding strengthening

Verify `[legal."rd-439-2007:art-110"].required_text` against the current BOE
consolidated art. 110 and the bundled corpus, and keep it scoped to the vigente
payment framework. The Modelo 130 casilla 15 carry mechanics are grounded by
`aeat-modelo-130-instructions`, which provides the required negative-result and
cap-by-casilla-14 instruction text. Current verification on 2026-06-29 confirms
there is no vigente art. 110.5 carry-forward sentence to import.

## Rationale

The `Decimal("0")` silent default is the root failure mode behind
the entire class of dead-binding regressions, not just Modelo 130.
Any modelo that grows a bound casilla whose binding selector is
later malformed, deleted, or shadowed will exhibit the same silent
zero. The fix is at the boundary between binding declaration and
value materialisation — exactly the layer the runtime classifies
"bound" casillas through.

Option C for the selector and Option Z2 for the zero-default
combine to enforce one structural invariant: **a bound casilla
either receives a value through its declared binding, or its
absence is declared at the selector level**. There is no third
path. Tests cannot smuggle a bound casilla value through `inputs`;
production code cannot silently zero-fill a dead binding.

The remaining `Decimal("0")` arrivals — through `max(0, x)`
clamping, through subtraction yielding zero, through a manual field
left blank, through a computed formula evaluating to zero on the
input domain — are all *legitimate* arithmetic or operational
zeroes. The runtime distinguishes them by their materialisation
path: computed casillas record a formula trace; manual casillas
record the operator-input absence; bound casillas record the
binding source. A C15 zero produced by Decision 1's first-period
suppression carries different provenance from a C15 zero produced
by a dead binding under the current runtime — but Decision 2
eliminates the dead-binding path entirely, so the only remaining C15
zero shape is the absent-by-design one.

## Consequences

### Positive

- Modelo 130 carry-forward functions correctly for 2T/3T/4T;
  suppresses correctly for 1T; the regression is structurally
  eliminated rather than test-masked.
- The dead-binding failure mode becomes observable across the
  entire registry. Other modelos with `input_kind = "bound"`
  casillas will surface their own dead bindings (if any) the moment
  the runtime no longer accepts the silent zero. This is a feature,
  not a regression: the campaign explicitly disallows shims and
  parallel chains, and silent zero is the most insidious shim of
  all.
- Test fixtures that currently pass `"15": Decimal("0")` (or any
  other bound casilla zero) as inputs will fail loudly. The fix is
  to delete those entries: bound casillas come from bindings, not
  from inputs.
- `CasillaObservation` provenance becomes a first-class audit
  signal: absent-by-design vs. resolved-from-source vs.
  computed-from-formula are now distinguishable downstream.

### Negative

- One-time sweep cost. Tests across the calculation suite that pass
  bound casillas as inputs need to be rewritten to either (a) pass
  the binding value through `binding_values`, (b) construct a
  `RegistryModeloObservation` and resolve it through the proper
  pipeline, or (c) accept the absent-by-design path. The
  remediation plan must enumerate these test sites before flipping
  the runtime.
- New selector field. `max_year_delta` adds a knob that authors of
  future bindings must understand. The TOML comment on the binding
  must document the same-ejercicio rule it enforces.
- The carry-forward selector still depends on the prior-quarter
  observation being supplied at calculation time. The application
  layer must arrange to load the prior 130/1T filing from
  persistence before calling `calculate_registry_snapshot` for
  130/2T. The plan must verify the calculation orchestration layer
  honours the previous-filing requirement walk (it already does for
  the income-reduction binding, so this is incremental, not new).

### Risks

- Sweep regression risk. If a bound casilla in another modelo has a
  binding that is currently dead-but-tolerated, the runtime flip
  will fail those calculations. The remediation plan must include
  a pre-flip audit step that enumerates every `input_kind = "bound"`
  casilla, resolves each one through the current binding selector,
  and reports the resolution status. Dead bindings discovered by
  the audit must be either repaired with the same Decision 1
  selector capability or marked absent-by-design via the same
  Decision 2 path before the flip lands.
- ADR/plan coupling. This ADR authorises the four decisions; the
  remediation plan must sequence them as a single Wave — selector
  capability first (no runtime dependency), pre-flip audit second,
  bound-casilla input rejection third, Modelo 130 binding revision
  fourth, regression tests fifth. Splitting across waves would
  reopen the silent-zero window between landings.

## Acceptance criteria

This ADR is accepted when the following gates hold in a successor
plan:

1. `_PreviousModeloSelector.max_year_delta` field exists, validates,
   and drops cross-year anchors when the cap is honoured.
2. `_initial_values` rejects inputs targeting bound casillas with
   `RegistryValidationError`.
3. Bound casillas resolve exclusively through the binding pipeline;
   absent-by-design (empty-anchor) bindings materialise
   `Decimal("0")` via an explicit constructor that records the
   provenance marker.
4. Modelo 130's `modelo-130-resultados-negativos-anteriores`
   binding declares `source_period_offset_from_target = -1` and
   `max_year_delta = 0`.
5. Three real-behaviour M130 tests (first-period suppression,
   second-period carry-forward, bound-input-rejection) live in
   `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`
   and pass.
6. Pre-flip sweep audit document enumerates every bound casilla
   across every modelo and the resolution status of its binding;
   dead bindings discovered are either repaired or annotated as
   absent-by-design before the runtime flip.
7. `required_text` on `[legal."rd-439-2007:art-110"]` matches the current
   BOE/bundled corpus for art. 110, and the Modelo 130 casilla 15
   negative-result mechanics are grounded through `aeat-modelo-130-instructions`
   rather than a retired art. 110.5 fragment.

## Amendment 2026-05-27 — Decision Z2 scope narrowed to previous-filing

During the P03 implementation the strict-rejection scope of
Decision Z2 ("inputs targeting any casilla with `input_kind =
"bound"` raises") proved too broad. Two factors warranted the
narrowing:

1. **Established production projection pattern**: the runtime
   helper `resolve_bound_casilla_inputs(revision, binding_values)`
   projects resolved binding values into a casilla-id-keyed
   mapping that production callers (aggregation, modelo actions)
   pass as `inputs` to `calculate_registry_snapshot`. This is not
   a masking pattern — the binding values are the source of
   truth and the projection is a runtime ergonomics convenience.
   Rejecting bound-casilla inputs unconditionally broke the
   established hexagonal contract.

2. **Non-numeric bound casilla shape**: ~30 bound casillas across
   the registry carry non-numeric `data_type` values (NIF, text,
   name, iban, etc.). The Decimal-only `values` map historically
   holds a `Decimal("0")` placeholder for them; the actual
   string value flows through a parallel provenance channel.
   The strict rejection broke ~30 unrelated tests that pass
   these bound casillas through inputs as the only available
   route.

**Amended Decision Z2 scope**: the rejection (Acceptance
criterion 2) applies ONLY to bound casillas whose binding's
`source` is `previous_filing`. The silent-zero hazard was
specific to previous_filing bindings (the M130 carry-forward
case) — the campaign's structural objective is foreclosed by
the narrower scope. Bound casillas with other binding sources
(profile, ledger, invoice, withholding, etc.) continue to
support the inputs fallback because they were never the silent-
zero hazard and the production code legitimately uses the
projection pattern above.

**Amended acceptance criterion 2**: `_initial_values` rejects
inputs targeting bound casillas whose binding `source ==
"previous_filing"` with `RegistryValidationError`. Subsequent
work tracked at `P06.S21` may either (a) extend the rejection
to all bound sources by first refactoring the production
projection helper to feed `binding_values` directly, or (b)
accept this amendment as the final architectural shape.

**Amended acceptance criterion 5 reflection**: the third M130
test (`test_modelo_130_bound_casilla_rejects_input_override`)
was re-scoped as
`test_modelo_130_previous_filing_bound_casilla_input_is_silently_ignored`
to match the amended contract: passing
`inputs={"15": Decimal("100")}` at 1T yields C15 = 0 with
`absent_by_design = True` (input silently discarded, not
rejected). The structural invariant the test pins — that
previous-filing bound casillas cannot be smuggled in through
inputs — is preserved.

## Amendment 2026-05-27 (B) — hardening turn after honesty review

The 2026-05-27 campaign-close honesty review surfaced 14 items
the campaign acquired or exposed but did not action: dead schema
surface (`_PreviousModeloSelector.relation` field accepting
arbitrary ignored values), private/public contradiction
(`_INCOMPLETE_*` constants re-exported through public `__all__`),
shim files that should be deleted
(`application/overview/_applicability.py`), one-off scripts not
discarded as promised (`bound_casilla_sweep.py`), a weakened
test contract that lost its design intent (silent-ignore vs
strict-rejection), assumed-not-verified M131 carry-forward
grounding, fictional 1T fixture seed, architecturally
unvalidated M036 manifest exclusion, untracked
`provisional_pending_specimen` usage drift, an undiagnosed
shared-worktree loader race, unaudited cross-campaign sweep
commits, and an authoring-time gap on the tautology gate.

**The campaign does not weaken; it hardens.** None of these
items is closed by acknowledgement alone. P07 phase tracks each
as a Step with a verification gate; nothing closes without
proving the harder contract is now enforced. The narrowing in
Amendment 2026-05-27 (A) is preserved as the runtime contract,
but the lost design intent from the original Decision Z2 is
re-established in S36 either by re-imposing strict rejection
after refactoring the production projection helper to feed
`binding_values` directly, OR by adding an authoring-time gate
test that walks every fixture and fails on previous_filing
bound-casilla-via-inputs patterns. The fixture-lying detection
must close — silent ignore is the silent-zero hazard in
disguise.

The 14 hardening Steps live at P07.S32-S46. Acceptance criterion
**8** is added: every P07 Step is closed (verified) before the
campaign is considered structurally complete; the prior 31-Step
closure is structurally necessary but not sufficient.

### P07.S36 outcome — strict-rejection contract recovered

The lost design intent from the original Decision Z2 is restored
via P07.S36 with a narrower-but-strict gate: previous-filing
bound casillas supplied via `inputs` MUST also appear in
`binding_values` under the matching binding id. The production
`resolve_bound_casilla_inputs` projection pattern is preserved
(the helper writes both maps from the same source); the
test-fixture lie pattern (input-only, no binding value) is now
rejected with a typed `RegistryValidationError`. The smuggle-via-
inputs hazard — the silent-zero hazard in disguise — is gone.

Amendment 2026-05-27 (A)'s "silent ignore" wording is superseded
for the smuggle case. The runtime contract for legitimate
projection (both maps populated with the same value) is unchanged.

## Amendment 2026-05-27 (C) — second honesty-pass hardening (P08)

A second campaign-close honesty review at 2026-05-27 — prompted
after P07 was declared structurally complete — surfaced 14
additional items the campaign acquired or assumed-but-did-not-
verify. The recurrence of the pattern (honesty-pass-only
disclosure) is itself a process finding tracked at P08.S58.

P08 covers 13 actionable Steps (S47-S59) plus the closing
verification:

### Regulatory cap-rule defects (highest priority)

- **S47** — M131 C11 ≤ C10 cap rule is documented in AEAT
  Modelo 131 instructions ("en ningún caso podrá figurar en la
  casilla 11 un importe superior a la cantidad positiva
  consignada en la casilla 10") but NOT enforced. The binding
  aggregation `op = "copy"` straight-copies the prior seed
  without capping. Either declare a verification predicate or
  extend the binding-aggregation surface with a clamp-to-
  casilla operator.

- **S48** — M130 C15 ≤ C14 cap rule (parallel finding from
  symmetry). Same defect shape, AEAT M130 instructions cited.

### Test contract hardening

- **S50** — `inputs` vs `binding_values` consistency check
  missing. The P07.S36 gate catches missing-binding-value but
  silently picks `binding_values` when both maps declare
  different values. Add an inconsistency rejection.

- **S51** — `CasillaObservation.absent_by_design` has no
  persistence-roundtrip test.

- **S52** — M130 3T and 4T quarters lack direct regression
  coverage (only 1T and 2T tested in P05).

### Architectural follow-ups

- **S49** — C03 silent computed→bound conversion (parallel
  campaign) never audited for AEAT grounding soundness.

- **S55** — S33 refactor was less aggressive than spec'd; the
  underscore-prefixed applicability constants are still
  externally consumed through the focused public module.

### Specimen + corpus authenticity

- **S53** — `provisional_pending_specimen = true` specimen
  authenticity unverified for M111/M130/M131.

- **S54** — M131 AEAT corpus HTML provenance unchecked.

### Process / governance

- **S56** — independent `vaultspec-code-reviewer` agent was
  never invoked. The vaultspec system rules mandate it.

- **S57** — `vault plan step check` silently drops plan body
  prose sections; raise upstream.

- **S58** — institutionalise the second honesty-review pass as
  a campaign-close process gate.

- **S59** — P08 closing verification.

The campaign continues to harden, not weaken. Acceptance
criterion 8 from Amendment (B) extends: every P08 Step closed
with a verification gate before the campaign is considered
structurally complete.
