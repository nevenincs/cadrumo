---
tags:
  - '#plan'
  - '#mutation-harness-extension'
date: '2026-04-25'
modified: '2026-07-17'
body_hash: 'sha256:f0bad8de1004c656d998e9b04726b0f864f126f23fffed7fbbdf1e18af3def54'
related:
  - "[[2026-04-25-mutation-harness-extension-research]]"
  - "[[2026-04-25-mutation-harness-extension-adr]]"
  - '[[2026-07-12-mutation-harness-extension-audit]]'
---
# `mutation-harness-extension` plan

> **Reconciled 2026-07-12 â€” delivered and superseded, not active.** The original ruleset-AST mutation harness was delivered, then corrected by the accepted mutation-harness fix. That ruleset architecture has since been replaced by revision-backed registry formulas; these rows must not be reopened as current work. Evidence is recorded in `2026-07-12-mutation-harness-extension-audit`.

Implementation plan for issue #338 â€” extend the mutation harness with
`percent`-rate, `brackets`-threshold, and `mul`/`div` scalar mutators
across the eighteen landed ruleset variants. Grounded in the ADR's
mutator taxonomy and AST-walking strategy.

## Proposed Changes

Eight files are added under `src/aeat/domain/formulas/_rulesets/`. No existing
file is modified except `docs/coverage/pipeline.md` (one new row in the
cross-cutting observables table). The existing operand-swap mutator
test module is left untouched.

### New private helper

- `src/aeat/domain/formulas/_rulesets/_mutators.py` â€” recursive AST walker,
  per-class mutators, `MutationCase` and `MutationCatalogueEntry`
  pydantic v2 models, the `_MUTATOR_REGISTRY` mapping, the
  `_NOT_MUTABLE_NODE_TYPES` allow-list, and the per-(ruleset Ã— node)
  cataloguer used by the kill-rate aggregator.

### New test modules

- `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py` â€”
  parametrised harness over every `PercentFormula` node in every
  landed ruleset variant. Mutates rate by `Â±1 pp`, asserts baseline
  clean + mutated discrepancy `â‰¥ 0.02 â‚¬` on a casilla downstream of
  the mutated node.
- `src/aeat/domain/formulas/_rulesets/test_brackets_threshold_mutation.py` â€”
  synthetic ruleset (Modelo-130-style step function), parametrised
  over each non-terminal bracket. Fixtures straddle each boundary by
  `â‰¤ 5 â‚¬`. Mutates `upper_inclusive` by `Â±1 â‚¬`; asserts the straddled
  fixture surfaces a discrepancy.
- `src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py` â€” parametrised
  harness over every `MulFormula` / `DivFormula` leaf scalar
  `Literal` in every landed ruleset variant. Mutates by `Â±1 %`;
  asserts discrepancy.
- `src/aeat/domain/formulas/_rulesets/test_mutator_exhaustiveness.py` â€” the
  orphan-node defense. Imports `aeat.domain.formulas.Formula`, asserts every
  concrete subclass is in the registry or in the allow-list with a
  documented reason.
- `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py` â€” aggregates
  per-mutator results across all eighteen ruleset variants; asserts
  kill-rate `â‰¥ 90 %`; emits the markdown summary table consumed by
  the exec summary.

### Documentation

- `docs/coverage/pipeline.md` â€” append a "Mutation-harness coverage"
  row to the cross-cutting observables table indicating âœ… for the
  four mutator classes (operand-swap, percent-rate,
  brackets-threshold, mul/div-scalar) plus the orphan-node defense.

### Vault exec summary

- `.vault/exec/2026-04-25-mutation-harness-extension/2026-04-25-mutation-harness-extension-summary.md`
  â€” captures the before/after flag counts per the issue DoD and
  enumerates the unflagged-nodes catalogue.

## Tasks

- Phase 1 â€” Build the private helpers (no external test surface yet).
  1. Implement the recursive AST walker yielding every compound node.
  2. Implement the four mutator helpers
     (`mutate_percent_rate`, `mutate_brackets_threshold`,
     `mutate_mul_div_scalar`; preserve `_swap_sub_op` from the
     existing operand-swap module by importing rather than copying).
  3. Define the `MutationCase` and `MutationCatalogueEntry` pydantic
     v2 models.
  4. Define `_MUTATOR_REGISTRY` and `_NOT_MUTABLE_NODE_TYPES`.
- Phase 2 â€” Wire each mutator class into its own test module.
  1. `test_percent_rate_mutation.py`. Walk every ruleset; build a
     parametrised case per `(ruleset, casilla, percent-node, Â±)`.
     Reuse fixtures already shipped with the per-modelo
     unit-tests where possible to minimise new fixture fabrication.
     Where no existing fixture exercises a percent path with non-zero
     base, contribute a minimal synthetic input set inline (still
     a pure unit-level fixture, no mocks).
  2. `test_brackets_threshold_mutation.py`. Build a synthetic ruleset
     `_SYNTHETIC_BRACKETS_RULESET` whose only computed casilla is a
     `BracketsFormula` step function. Parametrise per non-terminal
     bracket Ã— straddling fixture Ã— Â±direction.
  3. `test_scalar_mutation.py`. Walk every ruleset; build a
     parametrised case per `(ruleset, casilla, mul-or-div leaf, Â±)`.
     Today's surface: Modelo 303 casilla 66 (two years).
- Phase 3 â€” Defence + aggregator + summary.
  1. `test_mutator_exhaustiveness.py`. Assert every concrete
     `Formula` subclass has a registered mutator or an allow-list
     entry; assert no subclass appears in both.
  2. `test_mutator_kill_rate.py`. Run every mutator across every
     ruleset, collect `MutationCase` records, assert kill-rate
     â‰¥ 90 %, write the catalogue to the exec summary as part of
     the test (write under the exec slug, file name
     `2026-04-25-mutation-harness-extension-summary.md`). The
     write happens at test-runtime to keep the catalogue in sync
     with the harness output; the test fails if the write differs
     from the catalogue.
  3. Update `docs/coverage/pipeline.md`.
- Phase 4 â€” Local gates.
  1. `just lint && just typecheck && just test && just hooks`.
  2. `just test-cov` â€” verify 60 % floor on `src/aeat` still holds.
  3. Vaultspec code review against the seven safety invariants.
  4. Conventional-commit sequence per the handover prompt.

## Parallelization

Phases are sequential within a single agent. Test modules within
Phase 2 (1, 2, 3) are individually drafted but commit-sequenced per
the handover prompt's recommendation. Phase 4 gates run after every
commit; failures are diagnosed at the root, never bypassed.

## Verification

Mission success criteria, mapped to the issue DoD:

- [x] Parametrised harness covers every `PercentFormula`,
  `BracketsFormula`, `MulFormula`, `DivFormula` node across all
  eighteen landed ruleset variants. Today's populated surface:
  ~30 `PercentFormula` nodes + 2 `DivFormula` leaves; the
  brackets and mul surfaces are populated via the synthetic
  ruleset.
- [x] Existing `sub_op` operand-swap mutator preserved (file
  unchanged).
- [x] Baseline sentinel asserts on every mutated case before
  mutation is applied.
- [x] Every mutated case asserts `|delta| â‰¥ 0.02 â‚¬` on the affected
  casilla.
- [x] Aggregate kill-rate `â‰¥ 90 %`. Today's expected kill-rate is
  100 % across the populated surface; the floor leaves room for
  future legitimate "no observable effect" mutants.
- [x] `test_mutator_exhaustiveness.py` defends against orphan
  `Formula` subclasses.
- [x] `2026-04-25-mutation-harness-extension-summary.md` in the
  exec folder records before/after flag counts.
- [x] `docs/coverage/pipeline.md` updated.
- [x] `just test-cov` keeps 60 % floor green on `src/aeat`.
- [x] `just lint && just typecheck && just test && just hooks` all
  green on Windows.

## Self-review

This section records the explicit review against:

- `CLAUDE.md` (the project mandates checked into the repo): no
  drift on the public-API discipline, no new exception classes, no
  mocks, pytest-only, ty + prek, conventional commits, Pydantic v2
  on every model. âœ“
- `.claude/rules/vaultspec-system.builtin.md`: full vaultspec
  pipeline including this plan, the prior research and ADR, the
  forthcoming exec summary, and a final code review. âœ“
- The issue scope in STEP 3 of the handover prompt: three new
  mutator classes + preserved operand-swap + kill-rate aggregator
  + exhaustiveness defense + pipeline doc update. âœ“
- The audit finding citation in EPIC #316: the three classes
  flagged by the audit are exactly the three new mutator classes
  in this plan. âœ“
- The no-mocks discipline: the harness operates on real `Ruleset`
  instances + real fixtures + the real `Engine.audit_against`
  contract. No `unittest.mock` import anywhere. The synthetic
  ruleset for the brackets mutator is constructed via the public
  `Ruleset` API, not mocked.
- Coverage of every mutable node in every landed ruleset: the
  walker visits every formula tree under every ruleset variant in
  `ALL_RULESETS`. The `BracketsFormula` and `MulFormula` surfaces
  are zero today and the harness asserts that fact in the
  exhaustiveness test.
- The kill-rate target â‰¥ 90 %: enforced as a hard assertion in
  `test_mutator_kill_rate.py`.
- The orphan-node-type defense: every concrete `Formula` subclass
  must be either in the registry or in the allow-list with a
  reason; the test fails loudly otherwise.

Self-review outcome: **approved for execution**. No deviations from
the ADR. No scope creep. The test surface is constrained to
`src/aeat/domain/formulas/_rulesets/` plus a single doc-table touch.
