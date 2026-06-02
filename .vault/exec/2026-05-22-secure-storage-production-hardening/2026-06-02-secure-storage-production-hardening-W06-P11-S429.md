---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
step_id: 'S429'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W06-P11-S429-review]]'
---

# `secure-storage-production-hardening` `W06.P11.S429` Checkpoint

Wave `W06`; Phase `W06.P11`; Step `S429`.

## Description

- Reviewed the strict `PullResult` metadata slice with `vaultspec-code-reviewer`.
- Hardened `compute_from_pull` so `MetadataMatchState.MATCHES` must agree with actual metadata bound to the supplied snapshot.
- Extended pull-coverage validation so registry SHA drift is classified as metadata mismatch.
- Added focused regression tests for contradictory matching metadata and registry SHA coverage drift.
- Reran focused S429 gates where the current dirty registry state permits.

## Outcome

S429 is partially remediated but not closed.

Reviewer `Poincare` found one HIGH and one MEDIUM in-scope metadata strictness issue. Both production paths have been patched:

- `_require_metadata_match` validates modelo id, revision id, filing year, period, and registry SHA before compute.
- `verify_pull_coverage` compares `registry_sha` alongside the other metadata coordinates.

Validation:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_calc_sheets_pull.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/adapters/outbound/google/test_pull_result_roundtrip.py src/aeat/adapters/outbound/google/test_compute_from_pull.py src/aeat/adapters/outbound/google/test_verify_pull_coverage.py src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py` - passed.
- `uv run --no-sync pytest src/aeat/adapters/outbound/google/test_verify_pull_coverage.py src/aeat/adapters/outbound/google/test_pull_result_roundtrip.py -q` - 11 passed.

The full registry-backed S429 pytest gate remains blocked in the current dirty tree by unrelated Modelo 202 registry validation failures before Modelo 130 snapshots can load.

## Notes

Do not close `W06.P11.S429` until the Modelo 202 registry validation condition is resolved and the full focused S429 gate can be rerun successfully.
