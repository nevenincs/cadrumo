---
tags:
  - '#audit'
  - '#registry-localization-backend'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-06-08-registry-localization-backend-adr]]'
  - '[[2026-06-08-registry-localization-backend-research]]'
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` audit: `registry-localization-backend honesty review`

## Scope

This audit performs a campaign close honesty review of the `#registry-localization-backend` campaign. It evaluates the completeness, correctness, and adherence to codebase rules of all commits delivered under this feature on the `chore/eliminate-shims` branch.

## Findings

### G1 PASS — no naked env reads
All configuration access in the newly introduced manuals and localization packages is routed through `Settings` loaded via the standard dependency injection patterns. No direct calls to `os.getenv` or `os.environ` were added to production code.

### G2 PASS — typed pydantic at boundaries
The localization schema uses strict pydantic structures for model-local translation files. The `CasillaDefinition` is extended with typed dictionary structures (`localized_labels` and `localized_help`).

### G3 PASS — tr() for user messages
All newly added CLI command strings use the localization helper `tr(...)`. Parity audits of the locale catalogues remain clean.

### G4 PASS — no locale yml structure hand-edits
All modifications to the main locale catalog files `en.yml`, `es.yml`, `ca.yml`, and `hu.yml` were performed through the standard locales CLI, preserving parity.

### G5 PASS — no shims / re-exports / duplication
The localization loader filters and parses locales folder contents directly within the registry loader compilation pipeline, avoiding duplicate or shim layers.

### G6 PASS — no tautological calculation tests
The newly introduced validation tests for manuals references (`test_catalogue_verification.py`) and translation files (`test_registry_locales_parity.py`) assert schema structural properties, reference resolution, and compile-time integrity. They do not introduce hand-computed parallel-logic Decimal calculations.

### G7 partial-pass — test suite performance and typecheck warnings
The unit test suite has been successfully optimized using a fast role-typo similarity validator. However, running `just typecheck` fails globally on `ty check src` due to pre-existing diagnostics in the `tests/` directories, which are unrelated to this campaign. The typecheck diagnostics on files modified by this campaign have been fully cleared.

## Recommendations

1. Address the pre-existing typecheck diagnostics across the wider `tests/` folders in a separate hardening campaign.
2. Ensure subsequent campaigns on this branch continue to use the established locales CLI and do not introduce manual edits.

## Codification candidates

No project rule is promoted from this honesty review.
