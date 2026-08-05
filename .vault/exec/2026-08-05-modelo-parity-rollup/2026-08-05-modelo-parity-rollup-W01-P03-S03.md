---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:0d0068df4a106ca5fb38aaf97bb73890427847fed2215b1562f1d4342c93da3b'
step_id: 'S03'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Classify unsupported, open-ended, manual, upstream, deferred, and not-yet-measured coordinates without omission

## Scope

- `dev/registry/conformance/manager.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Used vault and code RAG to inspect the accepted finite annual-matrix contract and the current classification implementation.
- Verified the closed six-member classification vocabulary and the validatorâ€™s complete-key, exact-count, and duplicate-coordinate invariants.
- Added real failure tests for omitted classification keys, mismatched census counts, and duplicate exact coordinates.

## Outcome

S03 is complete within the current finite matrix. The validated D2025 coordinate `(100, 2025, 0A)` remains explicitly `not_yet_measured`; `unsupported`, `open_ended`, `manual`, `upstream`, and `deferred` remain visible as zero-count census members rather than fabricated coordinates or omitted keys. The validator rejects every incomplete or inconsistent classification census.

No production classification change was required because the existing implementation already enforced the accepted contract. No annual year, revision, manual/upstream reason, or deferred semantic status was inferred. The finite matrix remains separate from the 73-modelo/90-revision portfolio and will expand only through later exact-coordinate work.

## Notes

- A broader matrix selector run encountered one transient `RegistryLoadError` caused by concurrent registry cache fingerprint churn; the three new validator tests passed serially and the pre-existing broader conformance baseline was not reclassified as green or red from that transient.
- No mocks, fakes, stubs, patches, skips, xfails, copied business logic, staging, or commits were used.
- The S03 review audit records the explicit residual typing boundary in the shared test file.

## Verification

- `uv run --no-sync pytest -q -n0 dev/tests/test_registry_conformance_cli.py -k "annual_matrix_rejects"` â€” 3 passed; 87 deselected by the configured unit selector.
- `uv run --no-sync ruff check dev/registry/conformance/manager.py dev/tests/test_registry_conformance_cli.py` â€” all checks passed.
- `uv run --no-sync ruff format --check dev/registry/conformance/manager.py dev/tests/test_registry_conformance_cli.py` â€” 2 files already formatted.
- `uv run --no-sync basedpyright dev/registry/conformance/manager.py` â€” 0 errors, 0 warnings, 0 notes.
- `git diff --check` on the owned files â€” clean.
