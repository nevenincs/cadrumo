---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S137'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S137 Modelo Filing Extraction

Scope: extract residual modelo filing record list/get/file/supersession workflow behind the modelo application facade.

## Description

- Extracted `file_modelo_revision`, filing-record list/get, and verification-report list/get actions into `src/aeat/application/modelo/_filing_actions.py`.
- Kept `src/aeat/application/modelo/_actions.py` as the compatibility facade and preserved public `aeat.application.modelo` exports.
- Routed filing clean-state checks through `_verification_actions.py` instead of reaching back into `_actions.py`.

## Outcome

Filing and report CRUD workflows now live in a focused application module. `_actions.py` remains below budget at 761 lines after the filing extraction.
