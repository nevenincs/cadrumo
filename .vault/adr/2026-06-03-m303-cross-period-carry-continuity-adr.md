---
tags:
  - '#adr'
  - '#m303-cross-period-carry-continuity'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-m303-cross-period-carry-continuity-research]]"
  - "[[2026-06-03-m303-synthetic-generator-primitive-spec-adr]]"
  - "[[2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr]]"
  - "[[2026-06-02-m303-parser-engine-totals-impedance-adr]]"
---

# `m303-cross-period-carry-continuity` adr: M303 cross-period carry continuity diagnostic gate + anti-regression contract | (**status:** `accepted`)

## Problem Statement

Three tests in `src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py`
are red on HEAD after the primitive-encoding commit (`6e5a316a6`). The
in-period engine-recomputation correctness gate
(`test_verification_chain.py`, 47/47 green) does not exercise the
cross-period carry; the regression hid in that gap and surfaced only at
the cross-renta wrap (4T/N → 1T/N+1, casilla 110 auto-resolution from
the prior 4T's `iva.compensacion-disponible-fin-periodo`).

The carry chain is fully wired in the registry: relation
`modelo-303-rel-self-compensacion-anteriores` (source_output =
`iva.compensacion-disponible-fin-periodo`, target_binding =
`modelo-303-compensacion-pendiente-anteriores`, offset = -1,
period_alignment = previous_quarter) feeds binding-side casilla 110.
The relation resolver in `src/aeat/application/calculations/_relation_prefill.py`
pulls the saldo from the prior observation by exact casilla-id match.
What broke is **not the wiring** — that was unchanged by `6e5a316a6`
— but the **upstream production of `iva.compensacion-disponible-fin-periodo`**:
the per-rate primitive-encoded credit scenario no longer drives the
saldo formula chain to a positive value. The research document traces
every step of the chain at HEAD and identifies three candidate failure
modes that the diagnostic Phase will discriminate between by direct
observation of `result.values`.

## Considerations

The diagnosis must be evidence-driven, not speculative: the only
acceptable Phase-1 outcome is a printed casilla-by-casilla trace of
the year-N 4T run, pinning which downstream step in the
devengada-total → resultado-regimen-general → 64 → 66 → resultado →
generada-periodo → disponible-fin-periodo chain returns zero where
the chain narrative predicts a non-zero value. Without that
observation, any registry edit or generator edit is unsupported
guesswork.

Three candidate causes survive the carry-chain trace (per the
research):

- **A. Computed-casilla refusal silent-zero in devengada-total.** The
  primitive-encoding commit added `iva.autoconsumo.promotor.cuota` as
  an addend in the devengada-total formula. That leaf is itself
  computed (from `iva.autoconsumo.promotor.base * 0.21`). If the
  engine's evaluation order resolves the addend before its source
  leaf, or if the test's binding overrides shadow the computed value,
  the entire devengada total could collapse.

- **B. `result.values` shape drift.** The primitive-encoding commit
  may have added or removed keys in `result.values` so the relation
  resolver's exact-id `casilla_values.get("iva.compensacion-disponible-fin-periodo")`
  returns None, raising `RegistryValidationError` at the wrap. Test
  trace mode disambiguates by failure-class.

- **C. Cross-step subtraction-of-zero collapse.** A downstream step
  (e.g. `iva.compensacion-aplicada-periodo`'s `min(prior, max(0, c46))`
  evaluation) may consume a value differently after the encoding
  change, zeroing the chain mid-flight while preserving the per-period
  totals (devengada-total = c27, deducible-total = c45) that the v2
  spec's invariant required.

The fix shape is conditional on which Hypothesis fires. The plan
authorises three Phase-2 branches; only one will be executed.

## Constraints

- The registry author site is shared with concurrent campaigns. Per
  `aeat-git-worktree-safety` and `aeat-swarm-orchestration`, any edit
  to `src/aeat/_data/registry/aeat/modelos/303/` must be one atomic
  explicit-path commit and must `git log -1 -- <path>` before the
  edit to confirm no peer commit closed the gap.
- The fix MUST NOT regress the 47/47 verification-chain greens. The
  fix MUST land with both the carry-continuity tests green AND the
  verification-chain tests still green; running both gates is part of
  the Phase-2 verification.
- No new mock / xfail / skip. Per `aeat-quality-gates` and
  `aeat-roundtrip-discipline`, the anti-regression test must use
  the real engine, real registry authority, real encrypted-SQLite
  observation repo, and assert against engine-produced values
  (non-tautological).
- The fix MUST preserve the cross-renta legal grounding: LIVA art. 99
  (compensación de cuotas), arts. 115-116 (saldo a compensar /
  devolución), RD 1624/1992 arts. 29-30 (procedure). Every relation /
  binding / formula edit retains its `legal_refs` and `source_refs`.
- Workaround bindings supplied at the test layer
  (`modelo-303-autoconsumo-promotor-base = 0`,
  `modelo-303-profile-state-attribution-ratio = 100`, the five
  ledger_iva_aggregation cuota bindings = 0) MUST NOT mutate to mask
  the diagnostic; if Phase 1 surfaces that one of those workaround
  values now ranges, the workaround is updated in the test docstring
  and traced to a registry source binding (no silent values).

## Implementation

### Phase 1 — Diagnostic chain trace (no production edits)

A targeted instrumentation pass runs the year-N 4T branch of
`_calculate_303` and emits the full ordered casilla list described
in the research's "What the diagnostic Step must produce" section.
This is a one-shot evidence-gathering Step: either inline instrumented
into a temporary scratch script (deleted at end of phase) or attached
as a `print` Step in a debug pytest invocation. The output is captured
in the exec-step record verbatim. Phase 1 produces no code change to
production; it only produces the chain trace that pins which step is
broken.

The trace identifies one of the three Hypotheses (or surfaces a fourth
not anticipated). The exec-step record names which Hypothesis is in
play and points the Phase-2 Step at the matching branch.

### Phase 2 — Fix the broken link (one of three branches)

Conditional on the diagnostic:

- **Branch A (devengada-total).** Edit the registry formula or its
  evaluation order so the autoconsumo-promotor sub-chain resolves
  with the supplied profile binding = 0 cleanly. The likely
  intervention is in the registry compile / loader layer, not in the
  TOML — the formula and the base binding both look correct. If
  needed, the fix may extend the engine's `inputs` / `binding_values`
  precedence rules so a computed leaf whose ancestor binding is 0
  resolves to 0 deterministically.

- **Branch B (result.values keys).** Repoint the relation
  `source_output` to whatever computed-casilla id now carries the
  saldo (a rename surfaced by `6e5a316a6`), and confirm the legacy
  2009-y-siguientes revision has the matching shape. The fix is a
  one-line registry edit in both revisions per the central-config
  rule and the relation source_output declaration.

- **Branch C (cross-step collapse).** Identify the step whose
  evaluation changed, restore the prior-correct semantics either by
  fixing the TOML formula expression tree or by adjusting the
  primitive distribution in the synthetic generator so the upstream
  inputs reach the formula in their pre-regression shape. Per the v2
  spec Findings, the single-rate filer pattern preserves devengada-
  total and deducible-total; per-period c69 is NOT pinned by that
  pattern. If c69 is the divergent step, the fix may require
  extending the v2 spec to also preserve c69 (and saldo) — or
  accepting that the test scenario must move to a different credit
  shape that survives the new primitive encoding.

### Phase 3 — Anti-regression contract

A new test under `src/aeat/application/calculations/` that mutates a
primitive leaf in period N and asserts the carry-in saldo in period
N+1 tracks accordingly. The shape mirrors the anti-tautology pattern
the v2 spec ADR (Step §"Anti-tautology test") authored for
within-period totals, but raised one period up: it varies the credit
magnitude in 4T/N and asserts that 1T/N+1's casilla 110
auto-resolves to the same delta. The test runs the real engine, real
registry authority, real encrypted-SQLite observation store; the
assertion compares engine-produced values from two engine runs
(parameterised over credit magnitude), not against hand-computed
expectations.

Failure of this test would mean either the relation resolver no
longer reads `iva.compensacion-disponible-fin-periodo`, or the
engine no longer derives a saldo magnitude proportional to the
primitive input — both of which are the regression this campaign
exists to catch.

## Rationale

The research established that the wiring (relation, target binding,
casilla 110) is intact at HEAD; the v2 spec preserves per-period
totals (devengada-total = c27, deducible-total = c45); but neither
the in-period verification chain nor the v2 spec covers the
**cross-period saldo carry**. The shape of the regression — visible
only across a period boundary, hidden by a tightly-scoped success
gate — recurs in the wider M303 cluster every time the engine
boundary shifts. The anti-regression contract closes that hole
permanently: any future structural change to the per-rate primitive
distribution must keep this test green, which forces the change to
preserve the saldo magnitude across the cross-period wrap, not just
the per-period totals.

The diagnostic-first ordering is mandatory because the three
candidate causes lead to three different fix shapes (registry edit
vs evaluator-precedence edit vs spec extension). Picking a fix
before the diagnostic completes would either (i) miss the actual
broken step and leave the test red, or (ii) over-edit the registry
and break the in-period verification chain. The pattern is
inherited from the
`2026-06-03-m303-synthetic-generator-primitive-spec-adr` Findings
section: a fresh coder pickup reading the actual artefacts first,
then editing.

## Consequences

Gains:

- The cross-period carry surface becomes a load-bearing gate. No
  future M303 structural change can collapse the saldo magnitude
  silently between periods.
- The chain trace itself is a durable artefact: the diagnostic exec
  record names every casilla in the carry chain and the value the
  engine produces for each, so subsequent agents inheriting an M303
  saldo question have a worked example to compare against.
- The fix branch (whichever fires) leaves the verification chain
  green AND the carry tests green AND the legal grounding intact.

Difficulties:

- Phase 2 is conditional: the plan must explicitly authorise three
  branches, only one of which will execute. Reviewers reading the
  plan must understand the conditional branch is intentional, not
  unscoped.
- The fix may touch the synthetic fixture generator if Hypothesis C
  fires (primitive distribution extension). That would mean
  regenerating the 15 M303 corpus PDFs and updating their sidecars
  per the `fixture-provenance-declared-in-sidecar` rule. That side
  effect must NOT introduce new fixtures — the existing 15-fixture
  pool is preserved bit-for-bit on per-period totals, and only the
  primitive distribution under the c69-affecting leaf shifts.

Pitfalls:

- A "fix" that mutates the test's workaround binding values
  (autoconsumo-promotor-base, state-attribution-ratio, ledger cuota
  bindings) to compensate for a real registry-side defect would mask
  the defect. The plan's verification gates explicitly forbid
  modifying the workaround constants; if a Phase-2 Step needs to
  change them, the change must be ADR-traced to a registry binding
  source change, not a test-only mutation.

- The cross-cluster M390 surface (annual M303 consolidation) reads
  the same saldo casilla. If the fix lands at the saldo formula
  level, M390 inherits the fix automatically. If the fix lands at
  the relation resolver level, M390 may need a parallel review. The
  ADR scopes M303 only; M390 follow-up is a separate task referenced
  by the plan's verification gate.

## Codification candidates

- **Rule slug:** `cross-period-carry-anti-regression-required`.
  **Rule:** Every modelo whose registry declares a `kind =
  "previous_period"` relation between two periods MUST carry an
  anti-regression test that varies the source-period primitive
  input and asserts the next-period carry-in tracks proportionally,
  using the real engine and real observation store. The in-period
  verification chain is necessary but not sufficient; cross-period
  contracts need their own gate. Justification origin: this ADR,
  which surfaced a saldo-magnitude regression that the in-period
  47/47 green could not catch.
