---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S135'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S135 Modelo Verification Extraction

Scope: extract residual modelo verification predicates, findings, clean-state, and workflow-gate orchestration behind the modelo application facade.

## Description

- Extracted `verify_modelo_revision`, predicate DSL evaluation, verification finding builders, cross-period clean-state gates, DT12 advisory checks, M210 sentinel rewriting, and IVA-wallet verification findings into `src/aeat/application/modelo/_verification_actions.py`.
- Moved the shared workflow run/persist gate into `src/aeat/application/modelo/_workflow_gate.py`.
- Kept `src/aeat/application/modelo/_actions.py` as the compatibility facade for legacy private imports while the package-level `aeat.application.modelo` facade remains the consumer entry point.
- Preserved backend ownership of verification, clean-state, registry, and workflow policy; no business logic moved to CLI.

## Outcome

`src/aeat/application/modelo/_actions.py` is now below the hard 1250-line budget at 983 lines. The extracted verification module is 1027 lines, and the workflow gate helper remains below budget.
