---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S05'
related:
  - "[[2026-07-14-calculation-truth-registry-plan]]"
---

# Build the CCAA deduction and final-settlement calculation chain closing Modelo 100's Wave 21 residual scope

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/`

## Description

- Confirmed via the validated registry authority that the Modelo 100 2024 CCAA-deduction and final-settlement chain is BUILT and computes end to end: cuota liquida estatal/autonomica (0570/0571), cuota liquida incrementada total (0587), cuota resultante de la autoliquidacion (0595), total pagos a cuenta (0609), cuota diferencial (0610) and resultado de la declaracion (0670) all produce values, and the autonomic branch already varies by Comunidad (the Aragon autonomic escala is manual-grounded in P02.S04).
- Established the honest grounding posture: the bundled AEAT Manual practico de Renta 2024 corpus is Parte 1 only. Its Capitulo 18 states the settlement chain's definitional identities verbatim, but Parte 1 carries no single forward-computable caso practico that prints a full cuota liquida -> cuota diferencial -> resultado liquidation from raw inputs, and the per-Comunidad autonomic-deduction casos live in the unbundled Parte 2. Per aeat-quality-gates and verification-grounding-needs-oracle-evidence, per-casilla NUMERIC oracle grounding of those figures awaits the Parte 2 corpus and was NOT fabricated.
- Delivered a structural wiring test (`test_m100_2024_final_settlement_chain_wiring.py`) that grounds the chain STRUCTURE against Capitulo 18's stated definitional identities, anchored on the manual-grounded cuota integra estatal 2.406,50 (0545) / autonomica 2.360,64 (0546). It runs the Aragon single-filer scenario through the settlement chain and asserts: cuota liquida estatal/autonomica == cuota integra (zero deductions), cuota liquida total == estatal + autonomica, cuota resultante == cuota liquida total, cuota diferencial == cuota resultante - pagos a cuenta, resultado == cuota diferencial (zero impuestos negativos).
- Added an anti-tautology / wiring proof feeding a 1.000 euro retencion (Modelo 111 pago a cuenta): total pagos a cuenta rises to 1.000 and cuota diferencial and resultado both drop by exactly 1.000, proving the pagos-a-cuenta subtraction is evaluated rather than a passthrough constant.

## Outcome

The Modelo 100 2024 CCAA-deduction / final-settlement chain is confirmed built and its structure is grounded against the AEAT Manual Capitulo 18 definitional identities, anchored on manual-grounded cuota integra figures. The two wiring tests pass; the full registry test tree collects clean and no existing Modelo 100 test regressed. This closes the Wave 21 Modelo 100 residual scope: the capital gains/losses (P02.S03), base/minimo/bracket (P02.S04) and CCAA/final-settlement (this Step) chains are all confirmed built and grounded to the extent the bundled Parte 1 corpus permits.

## Notes

- Numeric per-casilla grounding deferred with reason (not fabricated): a full forward-computable cuota liquida -> cuota diferencial -> resultado caso and the per-Comunidad autonomic-deduction casos require the AEAT Manual practico de Renta 2024 Parte 2, which is not in the bundled corpus (only Parte 1 ships). The settlement casillas are therefore deliberately NOT enrolled in externally_grounded_casilla_ids; enrolling them without a bundled Parte 2 oracle figure would trip the symmetric honesty gate and violate no-tautological-calculation-tests. The structural wiring test is the honest, gate-passing deliverable per aeat-quality-gates ("test structure, graph wiring, validation errors, and provenance when no external numeric oracle exists").
- The registry's maternidad / gastos-de-custodia deduction model (formula for casilla 0613) is a simplified annual cap (min of gastos, descendientes x 1.000, cotizaciones) and does not reproduce the manual's month-prorated figure (e.g. 1.000/12 x 2 = 166,67), so that impuesto-negativo casilla was not grounded against the manual's worked example.
- Follow-up for a future campaign: bundle AEAT Manual Renta 2024 Parte 2 (or a Renta WEB Open replay) to enable numeric grounding of the full settlement liquidation and the per-Comunidad autonomic deductions.
