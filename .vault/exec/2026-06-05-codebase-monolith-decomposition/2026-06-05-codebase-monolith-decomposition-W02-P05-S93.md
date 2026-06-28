---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S93'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S93 UUID-Safe Ledger Fixtures

Scope: W02.P05 residual ledger CLI verification fixtures.

## Description

- Migrate ledger validation-path setup to seed the active profile through `register_minimal_profile`.
- Migrate ledger UX defect setup to keep display-name compatibility while using a bucket-id-matched active storage span.
- Remove stale in-process `config profile create tester` setup from validation tests that now conflicts with UUID-backed profile identity.

## Outcome

The affected real CLI integration suites now use a storage session whose active bucket id matches the registered profile identity. The formerly failing import setup paths pass. Focused verification reported 38 passing tests across `test_ledger_validation_paths.py` and `test_ledger_ux_defect_cluster.py`.

## Notes

No mocks, fakes, monkeypatches, skips, or xfails were introduced. The run emitted only third-party `ofxparse` deprecation warnings.
