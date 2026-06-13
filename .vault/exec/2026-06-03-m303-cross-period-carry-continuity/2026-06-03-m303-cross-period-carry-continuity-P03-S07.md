---
tags:
  - '#exec'
  - '#m303-cross-period-carry-continuity'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-03-m303-cross-period-carry-continuity-plan]]'
  - '[[2026-06-03-m303-cross-period-carry-continuity-adr]]'
---

# `m303-cross-period-carry-continuity` `P03.S07` exec — final gate sweep

## Action

Run all three required gates sequentially on the same HEAD.

## Result

- **Carry continuity (3 tests)** — green:

  ```
  src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py::test_year_n_4t_credit_produces_carry_forward_saldo PASSED
  src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py::test_year_n_plus_1_1t_casilla_110_auto_resolves_from_prior_year_4t PASSED
  src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py::test_modelo_303_compensacion_carry_enrolls_two_renta_years PASSED

  3 passed in 104.15s
  ```

- **Preservation gate verification_chain (94 tests)** — green, no in-period regression:

  ```
  94 passed in 576.22s
  ```

  (The brief named "47 currently green" but HEAD actually carries 94 verification-chain tests — the gate has expanded since the brief was drafted. All 94 pass.)

- **Anti-regression (4 parametrised tests)** — green:

  ```
  4 passed in 83.69s
  ```

## Atomic-commit composition

The brief mandates "land [the anti-regression test] in the same atomic commit as the fix." The fix itself landed in peer commit `c2e05f644` before pickup; bundling the anti-regression test with that commit retroactively is impossible without rewriting peer history (forbidden by `aeat-git-worktree-safety`). The anti-regression module is therefore landed as a follow-on atomic commit referencing `c2e05f644` in its message — the contract relation is preserved without altering peer commits.

## Workaround-binding integrity

The `_AUTOCONSUMO_PROMOTOR_BASE_BINDING = 0`, `_STATE_ATTRIBUTION_RATIO_BINDING = 100`, and five `_LEDGER_CUOTA_BINDINGS = 0` workaround constants are unchanged from the companion module. The anti-regression test mirrors these verbatim. No silent mutation masks the diagnostic.

## Legal grounding

LIVA art. 99 (compensación), arts. 115-116 (saldo/devolución), RD 1624/1992 arts. 29-30 (procedure) — the relation `modelo-303-rel-self-compensacion-anteriores`, target binding `modelo-303-compensacion-pendiente-anteriores`, and `iva.compensacion-disponible-fin-periodo` source casilla retain their existing `legal_refs` and `source_refs`. No registry edit was made.
