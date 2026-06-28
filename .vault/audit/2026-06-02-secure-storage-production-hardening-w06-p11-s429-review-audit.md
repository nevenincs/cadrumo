---
tags: ['#audit', '#secure-storage-production-hardening']
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` S429 Review Checkpoint

## S429-001 | HIGH | PullResult MATCHES verdict bypassed metadata identity checks

Reviewer `Poincare` found that `compute_from_pull` trusted `pull.metadata_match == MATCHES` without validating the attached `PullMetadata` against the supplied registry snapshot. A persisted, manual, or bug-mutated `PullResult` could therefore carry stale metadata with a matching verdict and still compute.

Resolved in code. `_require_metadata_match` now validates modelo id, revision id, filing year, period, and registry SHA against the supplied snapshot before allowing compute. The refusal context now includes workbook and snapshot revision/SHA values.

Regression coverage was added in `test_compute_from_pull_refuses_contradictory_matching_metadata_verdict`, but the current dirty worktree cannot execute that registry-backed test because unrelated Modelo 202 registry validation fails before Modelo 130 snapshots load.

## S429-002 | MEDIUM | Pull coverage comparison omitted registry SHA

Reviewer `Poincare` found that `verify_pull_coverage` compared modelo id, revision id, filing year, and period but did not compare registry SHA. That missed drift where the workbook coordinates still match but the registry slice has changed.

Resolved. `verify_pull_coverage` now includes `registry_sha` in metadata mismatch detection, and `test_verify_pull_coverage_detects_registry_sha_drift` covers the regression without using fakes, stubs, mocks, monkeypatches, skips, or xfails.

## S429-003 | BLOCKED | Registry-backed S429 gate cannot go green in current dirty tree

The S429 focused ruff gate passes. The registry-free structural subset passes:

- `uv run --no-sync pytest src/aeat/adapters/outbound/google/test_verify_pull_coverage.py src/aeat/adapters/outbound/google/test_pull_result_roundtrip.py -q` - 11 passed.

The full S429 registry-backed gate is blocked by an unrelated registry validation failure before the S429 assertions execute:

- `modelo 202 revision 2025-y-siguientes: dependency classification 'modelo-202-2025-y-siguientes-dep-200-cuota-base' does not cover relation refs ['modelo-202-2025-y-siguientes-rel-cuota-base-1p']`
- `modelo 202 revision 2025-y-siguientes: relation 'modelo-202-2025-y-siguientes-rel-cuota-base-1p' lacks source revision year coverage from 2023`

Status: keep `W06.P11.S429` open until the external Modelo 202 registry condition is resolved and the full S429 registry-backed gate can be rerun.
