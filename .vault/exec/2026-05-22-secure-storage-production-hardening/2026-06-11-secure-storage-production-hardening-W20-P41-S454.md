---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S454'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P41.S454 Filing/Modelo Localization And Error Hierarchy

Scope: `src/aeat/application/filing`, `src/aeat/application/modelo`, `src/aeat/locales`, and the error registry entries required by promoted modelo calculation errors.

## Description

- Audited filing/modelo for bare operator-facing exceptions, broad exception handling, and literal user-facing error-message construction.
- Promoted residual modelo calculation-input `ValueError` sites to typed `ModeloCalculateInputError` subclasses with structured context and translation keys.
- Promoted `ModeloRevisionPick` consistency failures to `ModeloRevisionPickError`.
- Registered the new errors in the central error-code registry.
- Added focused real-behavior coverage for typed, registered, localized modelo input errors.
- Updated locale catalogues only through `uv run --no-sync python -m aeat.locales`.
- Ran scaffold to absorb current-tree ledger invoice locale drift discovered by the global locale audit.

## Outcome

S454 implementation is complete. The S454-localized error paths now derive from the AEAT hierarchy, carry registry-backed codes, and render through locale keys. Locale parity, translation honesty, hardened locale coverage, error registry, exception hygiene, and focused modelo application tests pass.

## Notes

The explicit CLI casilla-normalisation entrypoint run is currently blocked before the S454 path by a moved-tree startup failure: the wizard catalogue is not registered at application startup, producing `Internal` exit code 6 during work-unit creation. This was recorded in the S454 audit as external current-tree work rather than mixed into the filing/modelo localization step.
