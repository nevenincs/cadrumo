---
tags:
  - '#plan'
  - '#m303-cross-period-carry-continuity'
date: '2026-06-03'
modified: '2026-06-03'
tier: L2
related:
  - '[[2026-06-03-m303-cross-period-carry-continuity-adr]]'
  - '[[2026-06-03-m303-cross-period-carry-continuity-research]]'
---


# `m303-cross-period-carry-continuity` `M303 cross-period carry continuity diagnostic + fix + anti-regression` plan

### Phase `P01` - Diagnostic chain trace

Run the year-N 4T branch of _calculate_303 with the credit scenario and emit a casilla-by-casilla trace of the carry chain to pin which step diverges from the chain narrative; identify which of Hypotheses A/B/C is in play.

- [x] `P01.S01` - Run _calculate_303 year-N 4T credit branch with instrumentation; `capture full result.values mapping; record each carry-chain casilla value in the exec record; `src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py`.
- [x] `P01.S02` - Identify which Hypothesis (A devengada-total / B result.values keys / C cross-step collapse) the trace pins; `name the broken step in the exec record; `.vault/exec/2026-06-03-m303-cross-period-carry-continuity/`.

### Phase `P02` - Fix the broken link

Conditional on Phase 1 diagnostic: execute the matching branch (A devengada-total chain, B result.values key drift, or C cross-step collapse) with one atomic explicit-path commit; verification chain tests AND carry continuity tests both green.

- [x] `P02.S03` - Conditional Branch A: extend engine evaluator-precedence so autoconsumo-promotor computed leaf with zero base binding resolves before devengada-total addends; `preserve verification chain greens; `src/aeat/domain/calculations/registry/`.
- [x] `P02.S04` - Conditional Branch B: repoint relation source_output to the post-rename saldo casilla id in both 2023-y-siguientes and 2009-y-siguientes revisions; `preserve legal_refs and source_refs; `src/aeat/_data/registry/aeat/modelos/303/`.
- [x] `P02.S05` - Conditional Branch C: extend the single-rate filer primitive distribution so c69 / saldo are preserved across the cross-period wrap; `regenerate the 15 M303 corpus PDFs if generator changes; update sidecars per fixture-provenance rule; `src/aeat/tests/fixtures/justificantes/_generate.py`.

### Phase `P03` - Anti-regression contract

Land a new cross-period anti-regression test that varies a primitive leaf in 4T/N and asserts 1T/N+1 casilla 110 auto-resolves proportionally, using real engine, real registry authority, real encrypted SQLite observation repo; non-tautological.

- [x] `P03.S06` - Author cross-period anti-regression test that parametrises credit magnitude in 4T/N and asserts 1T/N+1 casilla 110 auto-resolves proportionally using real engine + real registry authority + real encrypted SQLite observation repo; `src/aeat/application/calculations/test_modelo_303_compensacion_carry_anti_regression.py`.
- [x] `P03.S07` - Run both gates sequentially: carry continuity tests (3) + verification chain tests (47) + new anti-regression test; `all green; commit one atomic explicit-path fix + test bundle; `src/aeat/application/calculations/`.

## Description

Three tests in `src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py`
are red on HEAD after commit `6e5a316a6 fix(m303): wire primitive cuota leaves
into synthetic fixtures and extractor`. The reds are at the `assert
carried_saldo > Decimal("0")` line: the M303 cross-period saldo carry from
4T/N to 1T/N+1 collapsed to zero after per-rate primitive encoding landed.
The 47/47 in-period verification chain greens did not exercise the
cross-period contract; the regression hid in that gap.

The authorising ADR (`2026-06-03-m303-cross-period-carry-continuity-adr`)
identifies three candidate causes (A: devengada-total chain silent zero
from autoconsumo-promotor computed-leaf evaluation; B: `result.values` key
shape drift breaking the relation resolver's exact-id lookup; C: a
cross-step subtraction-of-zero collapse that preserves devengada-total /
deducible-total but loses c69 / saldo magnitude). The research
(`2026-06-03-m303-cross-period-carry-continuity-research`) traces the full
carry chain at HEAD: source binding -> `iva.cuota-devengada-total` ->
`iva.resultado-regimen-general` -> 64 -> 66 -> `iva.resultado` ->
`iva.compensacion-generada-periodo` -> `iva.compensacion-pendiente-periodos-posteriores`
-> `iva.compensacion-disponible-fin-periodo` (relation source_output) ->
observation persistence -> cross-renta wrap (offset -1, previous_quarter)
-> `modelo-303-compensacion-pendiente-anteriores` binding (casilla 110).

Phase 1 emits a casilla-by-casilla trace of the year-N 4T credit run and
identifies which Hypothesis fires. Phase 2 executes one of three fix
branches, conditional on Phase 1's diagnostic. Phase 3 lands a cross-period
anti-regression test that parametrises credit magnitude and asserts the
1T/N+1 casilla 110 auto-resolves proportionally — the contract that would
have caught the regression had it existed before commit `6e5a316a6`.

The fix MUST preserve the 47/47 in-period verification chain greens AND
the legal grounding (LIVA art. 99, arts. 115-116, RD 1624/1992 arts. 29-30).
Per the ADR's Constraints, the test's profile-gap workaround binding values
(autoconsumo-promotor-base = 0, state-attribution-ratio = 100, the five
ledger_iva_aggregation cuota bindings = 0) MUST NOT mutate to mask the
defect.




## Parallelization

Hard sequencing across Phases. P01 must produce the diagnostic before
P02 can pick a branch; P02's three Steps (S03/S04/S05) are mutually
exclusive — exactly one runs, selected by P01's Hypothesis pin. P03
runs after P02's fix is in the working tree (the anti-regression test
needs the carry to be green to assert proportional tracking).

Within P01, S01 (instrumented run) blocks S02 (Hypothesis identification);
no parallelism. P02's three Steps are conditionally exclusive and not
parallelised. P03's S06 (author the test) blocks S07 (final gate run +
atomic commit).

## Verification

The plan is mission-complete when ALL of the following gates pass on
the same commit:

- `uv run --no-sync pytest src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py -q` — three tests green.
- `uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_verification_chain.py -q` — 47 tests green (no in-period regression).
- `uv run --no-sync pytest src/aeat/application/calculations/test_modelo_303_compensacion_carry_anti_regression.py -q` — new anti-regression test green.
- Exec record for P01 names the Hypothesis pinned by the chain trace and includes the casilla-by-casilla value list.
- `vaultspec-core vault check all` clean across this plan, its ADR, and its research document.
- Workaround binding constants in `test_modelo_303_compensacion_carry_forward_continuity.py` are unchanged (autoconsumo-promotor-base = 0, state-attribution-ratio = 100, ledger cuota bindings = 0).
- Carry chain's legal grounding preserved: every relation, binding, and formula touched by the fix retains its existing `legal_refs` and `source_refs` (LIVA art. 99, arts. 115-116, RD 1624/1992 arts. 29-30).
- M390 cross-cluster follow-up (annual M303 consolidation reads the same saldo casilla) is acknowledged in the P03 exec record either as "fix landed at saldo formula level — M390 inherits" or "fix landed at relation resolver level — M390 needs parallel review (FU task filed)".
- Fix and anti-regression test land as one atomic explicit-path commit per the architecture-boundaries rule.
