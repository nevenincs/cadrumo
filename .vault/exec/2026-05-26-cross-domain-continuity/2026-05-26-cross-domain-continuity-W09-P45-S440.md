---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S440'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Replace cross-period clean-state tests' private renderer imports with a supported public CLI/rendering contract, preserving real localized notice, payload, and text coverage without underscore re-exports.

## Scope

- `src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/entrypoints/cli/ src/aeat/**/tests/`

## Description

- Replaced private CLI renderer imports in the cross-period clean-state test with the supported root `aeat.entrypoints.cli.app` contract through the shared CLI runner.
- Extended the encrypted M390 workflow to invoke public `work verify` in Catalan JSON and text forms, asserting result payload, notices, and rendered lines.
- Added optional censo activity-start setup so the public handler produces the same pre-activity advisory, then reloaded and compared canonical stored finding evidence.
- Ran adjacent/changed real workflow tests, owned Ruff, scoped whitespace verification, and the import-hygiene gate.

## Outcome

- Cross-period localization coverage no longer imports private renderer helpers or requires a new renderer facade.
- The public CLI preserves localized JSON/text behavior and canonical persisted evidence through reload.
- The targeted suite passed 2 tests in 16.28 seconds; owned Ruff and whitespace checks passed.

## Notes

- The initial focused hygiene run isolated S439 as the sole remaining failure. The final independent run after S439 passed all 11 hygiene tests. No S440 renderer-private import remains.
