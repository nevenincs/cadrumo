---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:09925e68416cd514f1f775c9f73123f947cc4209dc14c763ee427cb669958271'
step_id: 'S09'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Compose the filing-export limb from exact layout capability and official-byte evidence

## Scope

- `src/cadrumo/application/registry/`

## Description

- Add `FilingExportCoverageReport` and its fail-closed composer to the registry application facade.
- Enumerate every loaded modelo/revision and obtain filing-grade law-selected snapshots without injecting a revision identifier.
- Refuse a revision below filing grade, unreviewed filing evidence, failed snapshot selection, missing layout evidence, cross-limb disagreement, or stale source bytes with an explicit owner disposition.
- Rehash every materialized layout's `layout_authority` source with `verify_source_file` before admitting export capability.
- Add focused authority-backed tests for retained below-grade refusals, pending-review filing evidence, and changed official-byte digests.
- Generate the application API stub and refresh the registry API index entry.

## Outcome

- The closure limb retains the complete registry denominator. Model existence alone cannot produce filing capability: M036 remains a `below_filing_grade` refusal while filing-grade revisions require reviewed, law-selected evidence.
- Successful rows identify the canonical snapshot authority and source-byte digest; materialized layout sources are reverified from the source root. Any mismatch is a `stale_evidence` refusal rather than a filing claim.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/application/registry/tests/test_filing_export_coverage.py` passed: 3 tests in 28.64 seconds.
- `uv run --no-sync ruff check src/cadrumo/application/registry/_filing_export_coverage.py src/cadrumo/application/registry/__init__.py src/cadrumo/application/registry/tests/test_filing_export_coverage.py` passed.
- `uv run --no-sync ty check src/cadrumo/application/registry/_filing_export_coverage.py` passed.
- `uv run --no-sync python -m dev.docs.apidocs scaffold --check` reported no drift.

## Notes

- No registry catalogue, revision grade, period, export layout, or source-reference fixture was changed. The limb consumes existing validated authority and evidence only.
