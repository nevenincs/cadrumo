---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S314'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# investigate _legacy_iva_wallet_decision_key at _observations_repository.py line 131  -  only TRUE shim candidate from discovery2 sweep

## Scope

- `closed by 2e06db22c: source and history review found the legacy cleartext taxpayer_nif:year:period fallback already retired in c3118ec50`
- `hardened the encrypted roundtrip test to prove current latest and event records load via iva_wallet_decision_key and iva_wallet_decision_event_key and no cleartext latest-key record is written`
- `verified by 26 observations repository tests`
- `ruff`
- `and diff check`
- `ty remains blocked by the shared-tree missing stubs directory`
- `src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `c3118ec50c` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
