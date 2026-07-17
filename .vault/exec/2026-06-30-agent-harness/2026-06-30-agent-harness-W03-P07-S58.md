---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S58'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# Ship the figure-level numeric value-oracle gate for modelo 130 (casilla 07 vs the AEAT DR 130 worked example) computed through the registry engine with no new bundled corpus, delivering S56's value-correctness intent and the zero-tax-on-positive-income invariant

## Scope

- `src/aeat/agent/eval/tests/test_modelo_130_value_oracle.py`

## Description

- Add `test_modelo_130_value_oracle.py`: seed the AEAT DR 130 Instrucciones worked example (ingresos 12.000, gastos 4.000) through the live registry engine (`calculate_registry_snapshot`) and assert casilla 07 = 1.600,00 EUR — the published AEAT figure, grounded in IRPF Art. 99 / RD 439/2007 Art. 110.
- Encode the mandate invariant as a test: positive rendimiento neto must yield a strictly positive instalment (zero-tax-on-positive-income is suspect).
- Add a permanent anti-tautology proof: with gastos == ingresos the base is zero and casilla 07 = 0, proving the engine computes from the seeded inputs rather than returning a constant.

## Outcome

The operator golden eval now has a figure-level value-oracle (the mandate's "prove it with golden-task evaluations" value-correctness dimension), complementing S57's AEAT-grounded verification-contract (casilla-ID) dimension. Verified: 3 tests pass in the integration lane; ruff clean. The gate is auto-included in the standing `agent-harness-eval.yml` CI surface (it runs `pytest src/aeat/agent ... -m "integration or not integration"`).

## Notes

- This delivers S56's value-correctness INTENT without S56's scoped `src/aeat/_data/registry` corpus-sourcing campaign. The peer re-scoped S56 as "CROSS-CAMPAIGN ... the registry bundles no numeric worked examples ... needs a separate AEAT-corpus sourcing campaign". That blocking premise is too conservative for the figure-level oracle: the AEAT DR 130 worked example is already an accepted oracle in `entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py` and is reproducible through the engine with NO new bundled corpus — the inputs/expected ride in the eval's own fixture. S56 is left OPEN for the coordinator to reconcile (it remains valid as a broader multi-modelo corpus expansion); S58 closes the value-correctness gap now.
- Collision discipline: the four golden-runner files (`_runner.py`, `_models.py`, `modelo_130.toml`, `test_modelo_130_golden.py`) were under live peer WIP earlier this session (S57); I stood down from editing them and delivered this as a new, non-colliding file instead. Confirmed clean before authoring; committed path-scoped.
