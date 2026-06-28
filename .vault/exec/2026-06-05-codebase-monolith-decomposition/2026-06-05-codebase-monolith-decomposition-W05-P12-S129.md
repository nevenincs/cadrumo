---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S129'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P12.S129 Split Surface Verification

Scope: verify split test and fixture surfaces plus hard size-budget inventory.

## Description

- Verify justificante fixture generator split with Ruff, fixture tests, and import smoke.
- Verify application ledger/modelo split tests through focused application lanes.
- Verify adapter split tests across declaracion, sede, auth, secure objects, and runtime migrated repository lanes.
- Verify calculation-registry split tests after registry-schema and referential-integrity decomposition.
- Confirm hard filesystem inventory reports zero module offenders over 1250 lines and zero production callable offenders over 180 lines.

## Outcome

Split test and fixture surfaces are exercised by real behavior tests, and the hard size inventory is clean.

## Notes

The broad declaracion verification chain remains slow, but it passed when run in focused parts. No skipped or xfailed coverage was added.
