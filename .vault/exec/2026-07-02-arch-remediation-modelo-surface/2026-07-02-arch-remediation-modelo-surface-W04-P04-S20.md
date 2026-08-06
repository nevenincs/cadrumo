---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:1e38b1591c685690927bff856cb9e119cd3dddef43e5b4f437d859e1371f661e'
step_id: 'S20'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Declare the named generic-module allowlist so a new per-modelo branch in a generic module fails the gate unless the allowlist is consciously extended

## Scope

- `src/aeat/tests/test_generic_module_modelo_carveouts.py`

## Description

- Declare the named generic-module allowlist as `_RATCHET_BASELINE`; document the deliberate exclusion of the churned domain `_formula_runtime.py` (ADR-permitted `_evaluate_m###_*` op evaluators) and of modelo-keyed DATA modules.

## Outcome

A new per-modelo branch in a scanned generic module fails the gate unless the baseline is consciously lowered; the scope exclusions are documented, not silent. Commit `892faa383`.

## Notes
