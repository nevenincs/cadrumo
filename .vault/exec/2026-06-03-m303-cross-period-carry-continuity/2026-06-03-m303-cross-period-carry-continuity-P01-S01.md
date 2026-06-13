---
tags:
  - '#exec'
  - '#m303-cross-period-carry-continuity'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-03-m303-cross-period-carry-continuity-plan]]'
  - '[[2026-06-03-m303-cross-period-carry-continuity-adr]]'
  - '[[2026-06-03-m303-cross-period-carry-continuity-research]]'
---

# `m303-cross-period-carry-continuity` `P01.S01` exec — diagnostic chain trace

## Action

Probe the year-N 4T credit branch of `_calculate_303` to determine which of Hypotheses A / B / C the chain trace pins. The pickup HEAD is `445d3dd43` plus the local index changes from peer agents.

## Finding

Before any instrumentation, a `git log -1 -- src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py` re-read against HEAD (per `aeat-swarm-orchestration` read-before-act discipline) surfaced commit `c2e05f644 fix(m303): rewire carry-forward test fixture from form-number casillas to per-rate cuota bindings (post-2677c82d6 semantic-totals migration)` already on the branch — landed by a peer agent on `2026-06-04 00:07:31 +0200`, ~2h before pickup. Re-running the cluster confirmed all three originally-red tests are green:

```
src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py::test_year_n_4t_credit_produces_carry_forward_saldo PASSED [ 33%]
src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py::test_year_n_plus_1_1t_casilla_110_auto_resolves_from_prior_year_4t PASSED [ 66%]
src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py::test_modelo_303_compensacion_carry_enrolls_two_renta_years PASSED [100%]

3 passed in 104.15s
```

The peer commit's diff (`c2e05f644 -- src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py`) shows the chosen fix branch is neither A nor B nor C as named in the ADR. Strictly speaking, it is a fourth: **the test's input path changed**. Pre-`2677c82d6`, `iva.resultado-regimen-general` read the form-number casillas 27/45 (which the test injected as `casilla_inputs`); post-`2677c82d6`, it reads the COMPUTED semantic totals `iva.cuota-devengada-total` / `iva.cuota-deducible-total` derived from per-rate ledger cuota bindings, and the engine refuses computed-casilla inputs. The peer fix repointed the test fixture from form-number casilla inputs to per-rate cuota binding overrides — the only path that still injects a credit scenario into the chain.

This is congruent with Hypothesis C from the ADR ("cross-step collapse that preserves per-period totals but loses c69 / saldo magnitude"), but the resolution is at the **test fixture** layer, not the synthetic generator: the production engine and registry are unchanged. The form-number casillas 27/45 are display-only re-projections; the saldo chain is correct.

## Hypothesis pin

**Hypothesis C** with a Phase-2 resolution in the test fixture (not the registry, not the engine evaluator, not the synthetic generator). Phase-2 branches A/S03 (engine evaluator-precedence) and B/S04 (registry source_output repoint) are not in play.

## Phase 2 status

Phase 2 work is COMPLETE on the branch via peer commit `c2e05f644`. Steps `P02.S03`/`P02.S04`/`P02.S05` are all moot — none required execution because the chain itself is intact; only the test's injection path needed rewiring.
