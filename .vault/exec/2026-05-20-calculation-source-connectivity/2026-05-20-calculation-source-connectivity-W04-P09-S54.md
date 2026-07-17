---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S54'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Run feature surface quality gate for source mesh touched files

## Scope

- `.agents/skills/feature-surface-gate/SKILL.md`

## Description

- Run the feature-surface quality gate over the source-mesh touched files as a process step (not code): ruff format and check, ty type check, collect-only, and the targeted persistence/roundtrip and fingerprint test suites.

## Outcome

- ruff format: all touched files unchanged; ruff check: all checks passed.
- ty check on the six touched production modules: all checks passed.
- Persistence/roundtrip suite (source-mesh revision roundtrip, calculation repository roundtrip, ledger-filing-evidence roundtrip, domain-filing anti-tautology and secure-storage roundtrips, calculation-revision, domain-modelos secure-storage roundtrip): 39 passed.
- Registry-free invoice-fingerprint unit tests: 3 passed.
- Locale scaffold check: all four catalogues ok.
- Collect-only on the touched packages: clean (0 collection errors).

## Notes

Whole-tree collect-only surfaced two PRE-EXISTING collection errors unrelated to this feature: the MCP tests (`entrypoints/mcp/tests`) fail with `ModuleNotFoundError: No module named 'pywintypes'`, an absent-environment-dependency issue, not this diff.

CORRECTION (closeout review): an earlier draft of this record wrongly claimed the S52 integration tests were blocked by uncommitted modelo-131 peer WIP. That was a MISDIAGNOSIS. The closeout code review and a re-run proved the failures were feature-owned test regressions (a bucket-routing `StorageValidationError`, not the modelo-131 registry error). Root cause: the new unconditional invoice-catalogue self-load regressed every filing test that approves a draft against a non-active/sentinel bucket without an `invoice_catalogue` override. Fixed test-only across the full filing suite: added `invoice_catalogue=InvoiceCatalogue()` to the four `test_filing.py` fingerprint tests and to the shared `build_registry_filing_draft` approval helper (covering `test_calculate`, `test_testing_registry`, and `test_overview_verbs`), re-wired the two S52 integration tests to the conftest active runtime bucket, and enrolled the new `INVOICE_CATALOGUE_CHANGED` member in the `describe_stale_reason` coverage test. Full `application/filing/tests` suite now 267 passed, 0 failed; the modelo-131 registry is NOT a blocker (modelo 130 validates cleanly). No production change was required — the implementation stood; only test wiring was corrected.
