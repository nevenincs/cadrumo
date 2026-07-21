---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S377'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Seed dev/import_hygiene_scan.py exception allowlist from the pre-existing exceptions in test_public_api_boundaries.py and test_architecture_boundaries.py so the new gate starts from the same tolerated baseline

## Scope

- `dev/import_hygiene_scan.py`
- `dev/import_hygiene_baseline.json`
- `src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py`
- `src/aeat/entrypoints/cli/tests/test_architecture_boundaries.py`

## Description

- Re-ran the scanner against `HEAD` to confirm the exact current tolerated
  exception sets before seeding anything: 5 production Family-1 sites (all
  documented `CYCLE-BREAK-RATIONALE-WORKFLOW-REVIEW` sites in
  `application/review/_actions.py`, `application/review/_models.py`,
  `application/workflow/_models.py`), 6 Family-2 shim modules (the documented
  bridges), and exactly one genuine Family-3 multi-facade duplicate
  (`DEFAULT_IVA_GENERAL_RATE_PCT`, investigated and benign).
- Confirmed the two narrower gates' allowlisted exceptions are now EMPTY in
  practice: the registry gate's `_RAW_REGISTRY_ORCHESTRATION_IMPORT_ALLOWLIST`
  (six paths) and the CLI gate's `_PRIVATE_DOMAIN_IMPORT_EXCEPTIONS` (two
  entries) no longer have any matching live violation — every one of those
  sites was already repointed onto its public facade by Wave W01 through W03.
- Authored `dev/import_hygiene_baseline.json` with three named sections:
  `production_family1_cross_package_private_imports.sites` (the 5 CYCLE-BREAK
  sites, each carrying its `reason`), `family2_shim_modules.paths` (the 6
  documented bridges), and `family3_pinned_duplicate_symbols` (the 7 symbols
  retired from the app-layer umbrella facades in Wave W03.P88, which must never
  reappear, plus the `save_envelope` / `DEFAULT_IVA_GENERAL_RATE_PCT` tolerated
  entries the ADR investigated and closed with no action).
- Because the two narrower gates' own allowlists are now empty in practice,
  seeding the new gate's baseline is a NAMED, verified re-derivation of the
  live tolerated state, not a copy of stale entries — the baseline reflects
  exactly what the scanner reports today, cross-checked against both narrower
  gates' historical allowlist content.

## Outcome

`dev/import_hygiene_baseline.json` is checked in and read by
`src/aeat/tests/test_import_hygiene_gate.py` (S379). `ruff check` / `ruff
format --check` pass on every touched Python file.

## Notes

None. This Step's baseline-seeding work and S378's ratcheting-assertion work
landed together in one pass (see S379's record for the combined gate); S378's
own exec record predates this pass and documents only its precondition
scanner-correctness fix, left untouched here because it carries live
uncommitted peer annotation-sanitization edits in the shared worktree.
