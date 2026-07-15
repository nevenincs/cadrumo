---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S391'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# introduce _M210_ENGINE_LIVE feature flag defaulting False in Settings

## Scope

- `tests set True via fixture override`
- `keep the task 196 Path-B refusal active when the flag is False`
- `gate the engine-live branch in modelo_calculate so non-engine personas still hit the refusal until persona-replay gates pass`
- `src/aeat/core/settings.py + src/aeat/application/modelo/_actions.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `b6129ba9e4` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
