---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
step_id: 'S438'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Restore import-hygiene coverage in the owned M210 and M303 snapshot tests by migrating four public-facade symbols and rewriting two private-helper assertions through supported public behavior without test-only re-exports.

## Scope

- `src/aeat/application/aggregation/tests/test_m210_irnr_income_ledger.py src/aeat/application/modelo/tests/test_modelo_303_verification_source_snapshot_resolution.py src/aeat/{application/modelo`
- `domain/calculations/registry}/`

## Description

- Migrated the four owned public symbols in the M210 and M303 snapshot tests to their existing public facades.
- Replaced the M210 private-helper inspection with public `verify_modelo_revision` evidence and persisted `LedgerFilingEvidence` behavior.
- Replaced the M303 private extraction-profile/gate invocation with public `RegistryValidator` behavior against a live profile copy missing `verification_source`.
- Ran both owned real-behavior test modules, owned Ruff, scoped whitespace verification, and the project import-hygiene gate.

## Outcome

- All six owned private test-import statements are removed without a test-only or underscore re-export.
- The two rewritten assertions now prove supported behavior through public application/registry surfaces.
- The owned suites passed 5 tests in 20.94 seconds; owned Ruff and whitespace checks passed.

## Notes

- The import-hygiene gate still reports two independently owned failures: the peer-owned prorrata test's private `CalculationSourceDiagnostic` import (S439), and cross-period clean-state tests importing three private renderer helpers (S440). Neither is changed or claimed resolved here.
