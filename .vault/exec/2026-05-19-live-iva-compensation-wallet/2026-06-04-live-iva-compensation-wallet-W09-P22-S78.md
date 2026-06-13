---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S78'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# `live-iva-compensation-wallet` `W09.P22.S78`

## Scope

Non-IVA registry drift closeout for Modelo 714 Phase-A manual-casilla enrollment.

## Description

- Rechecked the Modelo 714 registry tree during the live-wallet closeout.
- Removed the remaining empty formulas fragment from the Modelo 714 Phase-A revision instead of encoding placeholder formulas.
- Preserved the manual casilla, construct, legal/source, and workbook parity declarations.
- Wrapped unrelated long recorder calls in the Modelo 714 fidelity test so the focused ruff gate can cover the non-IVA drift surface.

## Outcome

Passing gates:

- `pytest -q src/aeat/domain/calculations/registry/test_modelo_714_registry.py src/aeat/application/calculations/test_modelo_714_patrimonio_baseline_fidelity.py src/aeat/entrypoints/cli/test_modelo_714_stub_refusal.py` -> 12 passed.
- Included in the final focused gate -> 243 passed.
- Included in the focused ruff gate -> passed.

## Notes

Modelo 714 remains Phase-A/manual. The fix removes misleading empty formula metadata rather than adding fake formula targets or tautological formula parity.
