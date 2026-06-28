---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S60'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W05.P17.S60 full quality-audit baseline

Scope: `W05.P17.S60` - Run full quality-audit and persist updated baseline.

## Description

- Run the advisory `just quality-audit` surface after the W05 shim and policy
  cleanup slices.
- Run direct Ty and Pyright summary commands to capture counts hidden by the
  failing `typecheck-audit` subrecipe.
- Run compact structure, dependency, dead-code, complexity, duplication, and
  security lane summaries.
- Append the updated baseline to the full repo-health diagnostics audit.

## Outcome

Completed. The baseline remains advisory red, with green dependency and
dead-code lanes and red type, structure, production-complexity, duplication
inventory, and security-inventory pressure recorded in
`2026-06-04-full-repo-health-diagnostics-audit.md`.

Verification:

- `just quality-audit` completed at the top level.
- `uv run --no-sync ty check src --output-format concise` reported 800
  diagnostics.
- `uv run --no-sync pyright src/aeat --level warning --warnings` reported 2055
  errors and 514 warnings.
- `uv run --no-sync pyright src/aeat/domain src/aeat/application --level warning --warnings`
  reported 811 errors and 510 warnings.
- `just audit-deps` passed.
- `just audit-dead-code` passed.
- `just audit-duplication` reported 23 clone groups.
- `just audit-security` reported 11 blocking findings.

## Notes

No code was changed in this step. `typecheck-audit` still stops after the Ty
failure before reaching its full-tree Pyright line; the missing Pyright matrix
was collected directly and logged as follow-up recipe debt.
