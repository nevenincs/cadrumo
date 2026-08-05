---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b2ddab7a67c3a7f9db89a08f15623b91b0cb18ddf39869828c3ff20f626a95f6'
step_id: 'S02'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Compare each annual casilla population and attributes with its official form or layout source

## Scope

- `src/cadrumo/application/registry/_conformance.py`
- `src/cadrumo/application/registry/tests/test_conformance_profile.py`

## Description

- Used vault and code RAG, then read the accepted parity plan, ADR, research, and the full conformance/parser analogue files.
- Implemented a year-specific comparator over an authority-selected `RegistrySnapshot` using the existing official XML-dictionary parser.
- Kept BOE printed-form membership and XSD-only attributes explicitly `unsupported` or `unmeasured`; dictionary identity is not treated as printed-form parity.
- Added real bundled-registry tests and fixed census anchors for M100 2020â€“2025.

## Outcome

S02 is complete within its bounded contract. `compare_annual_casilla_population` compares non-internal registry casilla identities with the exact year-specific XML-dictionary casilla identities and reports missing/extra IDs, source/parser attributes, and explicit measurement statuses. It never chooses a newest or largest revision.

The measured M100 identity results are: 2020 `1531/1531/0`, 2021 `1693/1693/0`, 2022 `1852/1852/0`, 2023 `1929/1929/0`, 2024 `2093/2062/31`, and 2025 `2238/2205/33`, in registry casillas/dictionary casillas/identity divergences. Printed-form membership and XSD-only attribute parity remain unsupported or unmeasured by design.

The comparator is a bounded API and is not yet projected into the registry-wide CLI report. That remains an open follow-up for W01.P03.S03 and W01.P07.S13, where the finite annual matrix and classifications are defined. No M100 formulas, profiles, relations, legal sources, or peer WIP changed.

## Notes

- No newest-revision baseline or count equalization was introduced.
- No mocks, fakes, stubs, patches, skips, xfails, copied business logic, staging, or commits were used.
- The mandatory code-review skill was invoked. The delegated reviewer persona stalled before returning; the supervisor completed the exact-diff review and recorded the residual report-projection finding in the dedicated S02 audit.

## Verification

- `uv run --no-sync pytest -q src/cadrumo/application/registry/tests/test_conformance_profile.py` â€” 25 passed.
- `uv run --no-sync ruff check src/cadrumo/application/registry/_conformance.py src/cadrumo/application/registry/tests/test_conformance_profile.py` â€” all checks passed.
- `uv run --no-sync ruff format --check src/cadrumo/application/registry/_conformance.py src/cadrumo/application/registry/tests/test_conformance_profile.py` â€” 2 files already formatted.
- `uv run --no-sync basedpyright src/cadrumo/application/registry/_conformance.py src/cadrumo/application/registry/tests/test_conformance_profile.py` â€” 0 errors, 0 warnings, 0 notes.
- `git diff --check` on the owned files â€” clean.
