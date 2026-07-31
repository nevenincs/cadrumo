---
tags:
  - '#audit'
  - '#registry-formula-runtime-boundary'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:138654f1f55748e740c10d3803c911cdbb4bc988fd58ddc1d1f591576d1fbc3f'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
  - "[[2026-06-02-registry-formula-runtime-boundary-audit]]"
---

# `registry-formula-runtime-boundary` Code Review

## FORMULA-RUNTIME-S25-001 | PASS | Audit-only slice preserves formula runtime code

No issue found. The slice-owned diff records the extraction assessment
and closes P04.S25 while leaving
`src/aeat/domain/calculations/registry/_formula_runtime.py` untouched.

## FORMULA-RUNTIME-S25-002 | PASS | Public calculation facade is preserved

No issue found. The audit keeps `calculate_registry_snapshot`,
`RegistryCalculationResult`, `RegistryCalculationEntry`,
`read_parameter`, and the M210 sentinel constants stable through
compatibility re-exports.

## FORMULA-RUNTIME-S25-003 | PASS | Previous-filing coupling is deferred

No issue found. The recommendation defers initial-value and
previous-filing guard extraction until `_PreviousModeloSelector`
ownership is settled by the binding resolver work.
