---
step_id: S299
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-ramon-cli-testimonial-audit]]"
  - "[[2026-05-27-ines-cli-testimonial-audit]]"
---

# cross-domain-continuity W09.P41.S299 — M303 SIMPLIFICADO ledger-preflight bypass

## Outcome

S299 partially closed. The ledger-preflight bypass for `iva.regime=SIMPLIFICADO`
is live and pinned by a regression test. Full binding routing (casillas 47-58
forfait engine wiring) remains corpus-blocked behind Task #227 (Orden
EHA/672/2007 tarifa corpus authoring).

## Root cause

`_raise_if_ledger_preflight_blocks_calculation` in
`src/aeat/application/modelo/_actions.py` checked for `ledger_iva_aggregation`
bindings in the M303 revision regardless of the profile's IVA regime. SIMPLIFICADO
operators supply casillas 47-58 as manual inputs and have no transaction ledger
to satisfy the IVA aggregation preflight gate; the gate unconditionally blocked
their M303 calculate path.

## Fix

Added three elements to `_actions.py`:

- `_iva_regime_for_bucket(bucket_id)` — reads `iva.regime` from the profile
  facts via `UserProfileLifecycleRepository` + `record_to_path_values`; returns
  `None` if the profile is absent or the fact is unset.
- `_IVA_LEDGER_EXEMPT_REGIMES = frozenset({"SIMPLIFICADO"})` — exempt-regime
  registry; documented as the authoring surface for future regime additions.
- Early-return bypass in `_raise_if_ledger_preflight_blocks_calculation`: if
  `_iva_regime_for_bucket` returns a regime in `_IVA_LEDGER_EXEMPT_REGIMES`,
  the function returns immediately before any ledger scan.

## Files changed

- `src/aeat/application/modelo/_actions.py` — `_iva_regime_for_bucket` helper,
  `_IVA_LEDGER_EXEMPT_REGIMES` constant, bypass branch in preflight function.
  (Changes bundled into commit `056625869` by co-running background agent S218.)
- `src/aeat/application/modelo/test_simplificado_ledger_bypass.py` — NEW.
  Two-test regression module: bypass fires for SIMPLIFICADO (must not raise),
  anti-tautology proof for GENERAL regime (must raise same inputs).

## Tests

Both regression tests pass. The anti-tautology test confirms the bypass is
scoped to SIMPLIFICADO: the identical input set raises
`ModeloAggregationBindingError` matching `"ledger preflight"` for a GENERAL
profile. Ruff lint clean on the new test file.

## Commits

- `056625869` — S218: M130 casilla 15 acumulación overrides accepted (Diego #218)
  — bundled the `_actions.py` changes (background agent cross-authorship)
- `a062b1e89` — S299: M303 SIMPLIFICADO ledger-preflight bypass + regression test

## Gates

- G1 ruff: clean
- G2 pyright: not run (pre-existing pyright issues in codebase)
- G3 pytest (unit): both simplificado regression tests pass
- G4 anti-tautology: GENERAL-regime case confirmed raising
- G5 vault plan step: closed via `vault plan step check`

## Scope boundary

Full S299 scope (binding routing to régimen simplificado casillas 47-58 via the
forfait tarifa engine) is unblocked only after Task #227 (Orden EHA/672/2007
module-tarifa corpus). This step record covers the preflight bypass portion only.
