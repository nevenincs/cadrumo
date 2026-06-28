---
tags:
  - '#adr'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - "[[2026-05-04-calculation-authority-evidence-tiering-research]]"
---


# `modelo-chain-tier-passage` adr: `Three-tier passage spec for modelo linkage-chain implementation work` | (**status:** `accepted`)

## Review State

This ADR is accepted as the implementation contract that sequences
the chain-cohesion work toward an end state where the registry can
sustain a multi-year synthetic filing history whose dependency chains
calculate correctly.

The chain-cohesion work to date has landed Tier 1 partial coverage
(modelo-internal calculation passes per-revision schema checks) and
Tier 2 full coverage for the six canonical feeder→summary chains
(111→190, 115→180, 123→193, 130→100, 131→100, 202→200). Tier 3 has
no implementation yet; this ADR pins the requirements so subsequent
slices can land it.

## Problem Statement

Chain work to date verifies two distinct concerns: that a relation
is declared in the right shape (cohesion) and that the resolver
aggregates source observations into the expected target value
(resolution). Both are within-year, single-pass checks. The
end-state the project is aiming at is broader: a continuous synthetic
taxpayer whose AEAT filings span multiple tax years, whose IVA
positions offset between repercutida (collectable, output) and
soportada (payable, input) quarter after quarter, whose negative VAT
positions carry forward (arrastre) across periods, whose IRPF
retentions in 111 / 115 / 123 accumulate into the 100 final
settlement, whose capital losses and pension contributions carry
forward across years, and whose receiver modelos (190, 180, 193, 100,
200, 390) each compute internally consistent values from observed
source filings.

Without an explicit tiering of the requirements, the chain work
risks landing point fixes (one chain, one year, one direction) that
do not compose into the end-state contract. Three tiers carve the
work into observable passage points so each slice's contribution is
visible against the goal.

## Decision

This ADR proposes the following three-tier passage spec.

### Tier 1 — Round-trip per modelo, single period

A modelo passes Tier 1 when, given a deterministic synthetic input
covering its casilla schema, its registry-declared formulas and
bindings produce deterministic outputs in one concrete period. The
input is typed as a Pydantic strict-frozen model whose fields are
the modelo's casilla ids; the output is the same modelo's resolved
casilla values plus its export-record bytes (when an export layout
exists).

Tier 1 requirements:

- Every modelo whose casilla schema is complete enough to compute
  outputs has at least one round-trip test that pins concrete
  Decimal inputs and concrete Decimal outputs for one period.
- Every formula declared on the revision is exercised by at least
  one round-trip test (no orphan formulas).
- Where the modelo has an export layout, the round-trip test asserts
  the full byte stream matches a fixture string at the registry's
  declared offsets and lengths.
- Round-trip tests use no mocks, stubs, or fakes; the registry's
  own runtime is the only execution path.

Tier 1 explicitly does not require cross-modelo data flow. Each
test exercises one revision in one period from synthetic inputs to
its own outputs.

### Tier 2 — Cross-modelo chain resolution within one tax year

A chain passes Tier 2 when, given a complete set of source filings
covering the relation's source_periods, the receiver's relations
resolve to the expected aggregate value. Tier 2 is the slice already
landed for the six canonical feeder→summary chains.

Tier 2 requirements:

- Every canonical feeder→summary chain has a resolution test pinning
  per-period source values and per-relation expected aggregates.
- Aggregation ops (sum, copy) produce arithmetically-checked Decimal
  values, not just non-empty results.
- Both quarterly-only and dual quarterly+monthly receiver paths are
  exercised (e.g., 100's 111-retenciones-trimestrales alongside
  100's 111-retenciones-mensuales with zeroed monthly observations).
- The cohesion test pins the relation declaration (source_modelo,
  source_output, target_binding, dependency_role) so a regression
  cannot silently drop the chain.

Tier 2 does not require multi-year history. Source filings are
synthesized fresh for the test's one tax year.

### Tier 3 — Multi-year offsetting ledger

A synthetic taxpayer passes Tier 3 when, across at least three
consecutive tax years, every receiver modelo's calculated values
match the values its declared feeders produced for the same tax
year, and every offsetting carry-forward (arrastre) is honoured.
Tier 3 is the end state the project is aiming at.

Tier 3 requirements:

- A multi-year synthetic-taxpayer fixture spans at least three
  consecutive tax years and supplies, per year, the synthetic
  spending, income, retentions, IVA repercutida (collectable),
  and IVA soportada (payable) data needed to drive every modelo
  in scope.
- The IVA chain offsets per-quarter: 303 computes
  ``resultado = repercutida - soportada`` per quarter, and 390
  reconciles the four quarterly outputs into the annual summary.
  Negative-resultado quarters carry forward to the next quarter
  (arrastre a periodos siguientes); a year-end negative balance
  carries to the following year unless a refund was requested.
- The IRPF retention chain accumulates: 111 / 115 / 123 quarterly
  retentions sum into the matching annual receivers (190 / 180 /
  193) and into 100's retentions-periodicas binding. The 100
  settlement reduces the cuota by the accumulated retention, and
  any negative settlement results in a refund recorded against the
  next year's opening ledger.
- IRPF pago fraccionado credits accumulate: 130 / 131 quarterly
  pagos sum into 100's pagos-fraccionados binding and reduce the
  cuota. A negative cuota results in a refund recorded against the
  next year's opening ledger.
- Year-over-year carry-forwards apply: capital losses (LIRPF arts.
  48 / 49), pension-contribution unused limits (LIRPF art. 52),
  and IS bases imponibles negativas (LIS art. 26) carry forward
  per their statute-defined windows.
- The fixture is reproducible: identical inputs produce identical
  outputs across runs. Random data is not permitted; the fixture
  is a typed Pydantic model with explicit values per year, per
  quarter, per casilla.
- The Tier-3 test asserts that, after running the entire multi-year
  filing simulation, the registry's resolver produces values that
  exactly match the fixture's expected per-year, per-modelo target
  values. Any discrepancy indicates either a registry calculation
  bug or a fixture inconsistency.

### Sequencing

Tier 1 must complete before Tier 3 can run because Tier 3 requires
each modelo to compute its own outputs deterministically before
those outputs can flow through chain resolution. Tier 2 is already
landed for the canonical chains and stays valid; Tier 3 reuses
Tier 2's resolver but on a synthetic-feeder ledger that itself
came from Tier 1 round-trips.

The natural sequence is:

1. Inventory which modelos have complete enough casilla schemas to
   pass Tier 1 round-trip. Modelos still at the foundation skeleton
   stage (e.g., 303 / 390 with only the ejercicio + periodo header
   casillas) are out of Tier 1 scope until their schemas land.
2. Land Tier 1 round-trip tests for every modelo with a complete
   schema, in dependency order: feeders (130 / 131 / 111 / 115 /
   123 / 202) first, then receivers (100 / 190 / 180 / 193 / 200),
   then once 303 / 390 schemas land, the IVA chain.
3. Once Tier 1 covers every modelo in a chain, write the Tier 3
   multi-year fixture for that chain and assert the multi-year
   roll-up.

## Constraints

The fixture must be a strict-frozen Pydantic model. Random data is
forbidden because the contract is "identical inputs produce
identical outputs" and randomness defeats that contract.

The fixture must use ``Decimal`` for every monetary value. Floats
introduce rounding drift that masks calculation bugs.

The fixture must declare per-year, per-quarter (or per-month, where
the feeder is monthly), per-casilla values. The fixture is the
input; the registry resolver is the only thing that computes
outputs from it.

The Tier 3 test must not synthesize "expected" target values by
running the resolver itself. The expected values are pinned in the
fixture as separate fields so the test compares two independent
sources of truth: the registry's output and the analyst's
hand-computed expectation.

The Tier 3 test must walk every chain in scope (not a sampled
subset). Skipping chains hides regressions that only show up under
multi-year offsetting.

## Implementation Direction

The next concrete commits implement Tier 1 in dependency order:

- Step 1: Inventory modelos by casilla-schema completeness. Produce
  a structural test that fails when a modelo claims to be in scope
  for round-trip work but its schema cannot satisfy a synthetic
  input.
- Step 2: Round-trip test for the simplest feeder modelo whose
  schema is complete (likely 130 or 131; quarterly IRPF pago
  fraccionado with a small casilla set and well-understood math).
- Step 3: Round-trip tests for the remaining feeders (111 / 115 /
  123 / 202) one slice at a time.
- Step 4: Round-trip tests for the receivers (190 / 180 / 193 /
  200 / 100) once their feeders have round-trip coverage.
- Step 5: Tier 3 multi-year fixture skeleton — the typed Pydantic
  model, the per-year ledger, the IVA arrastre logic. No assertion
  yet; this slice just builds the fixture.
- Step 6: Tier 3 first multi-year run — three years of IRPF
  retention chain, asserting per-year 100 settlement values.
- Step 7: Tier 3 IVA chain — three years of 303 quarterly with
  repercutida / soportada offsetting and 390 annual roll-ups, once
  303 / 390 casilla schemas have landed.
- Step 8: Tier 3 cross-chain — combine IRPF and IVA into one
  taxpayer fixture and assert the full multi-year filing history
  is internally consistent.

## Rationale

Three tiers carve the work along the natural axis of cross-modelo
dependency depth. Tier 1 has no cross-modelo flow; Tier 2 has
within-year cross-modelo flow; Tier 3 has cross-year cross-modelo
flow with offsetting. Each tier is an observable passage point: a
slice either passes its tier or it does not.

The "in the green" criterion the project is aiming at is precisely
Tier 3: a multi-year filing history whose dependency chains all
compute correctly. Naming it as a tier passage gives every interim
slice a destination to point at, and lets the rebuild plan track
progress as a count of passing tiers per modelo / per chain.

The decision deliberately keeps the fixture data hand-curated and
strict-frozen rather than generated. The contract is determinism,
and determinism is incompatible with random fixtures. A taxpayer
schema that produces different audit traces between runs is the
opposite of what the calculation-truth registry exists to deliver.

## Consequences

The chain-cohesion work gains a target to point at. The current
test suite covers Tier 2 for six chains; Tier 1 has implicit
coverage through scattered casilla tests but no per-modelo
round-trip contract; Tier 3 has no coverage at all.

The next implementation slices have a clear order of operations
and a clear definition of done per slice. Each slice's commit
message can name the tier and the modelo whose passage it advances.

The end state — sustaining a multi-year synthetic taxpayer whose
dependency chains calculate correctly across IRPF retentions,
pagos fraccionados, IVA offsetting, and IS prepayments — is
explicitly named as Tier 3 and explicitly named as the project's
"in the green" criterion. Subsequent ADRs that affect chain
behaviour reference this tier model.

## Explicit Non-Decisions

This ADR does not pick the order of modelos within Tier 1 beyond
the dependency-order guideline. The exact pick is left to the slice
that lands the work.

This ADR does not specify the Pydantic shape of the multi-year
fixture. That shape lands in the Tier 3 fixture-skeleton slice
(Step 5 above), at which point the fixture's API is itself an ADR
target.

This ADR does not commit to a specific number of years for the
Tier 3 fixture beyond the "at least three consecutive tax years"
floor. The fixture's first iteration may go further if the
carry-forward statutes the project chooses to exercise (e.g., LIS
art. 26 base imponible negativa carry-forwards) require it.

This ADR does not prescribe how Tier 3 surfaces failures in CI.
Test placement, runtime budget, and CI gating are operational
decisions outside this contract.
