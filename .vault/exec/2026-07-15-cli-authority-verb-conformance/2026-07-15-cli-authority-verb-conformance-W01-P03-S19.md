---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:824bde65fc3e7f64759bd33452a2513206fc3287edebfadde40e9fa283c2d2a3'
step_id: 'S19'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the core state-root isolation test against real isolated secure storage

## Scope

- `src/cadrumo/core/tests/test_isolation_fixture_state_root_coverage.py`

## Description

- Inspect the canonical `isolated_cli_backend`, its real file-backed `isolated_profile_storage_root`, and the live `_STATE_ROOT_DERIVED_DIRS` taxonomy.
- Run `uv run --no-sync pytest -vv -n 0 -m integration src/cadrumo/core/tests/test_isolation_fixture_state_root_coverage.py` serially.
- Record exact node outcomes and the temporary-root boundary proved by the dynamic taxonomy assertions.

## Outcome

Both exact nodes passed in 1.71 seconds: `test_isolated_cli_backend_covers_every_state_root_derived_dir` and `test_isolated_cli_backend_yields_a_directory_under_tmp_path`.

The real fixture configures the file secure-store backend with `tmp_path / "cadrumo-storage"` as the empty state root and `tmp_path / "secrets"` as its independently provisioned sibling. The first node dynamically traverses all 24 current `_STATE_ROOT_DERIVED_DIRS` fields, requires each to be populated, and requires every path to equal or descend from the test-scoped `tmp_path`; this covers the secret-store sibling as well as root-derived tokens, blobs, audit, logs, caches, durable outputs, financial catalogues, usage-ratio file, and registry parity archive. The second node separately proves that the yielded storage root itself descends from `tmp_path`.

## Notes

An initial serial command without `-m integration` collected both nodes but deselected both because the repository default selector is `-m unit`; it was not counted as verification. The corrected explicit integration run executed both nodes. No source or test file was changed.
