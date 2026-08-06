---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:7f1f63780c22d08581153cbf48e4ac68106273c7a2e8bd8ad19fbd3c1af9323e'
step_id: 'S56'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Fail documentation checks when an advertised channel lacks matching acquisition evidence

## Scope

- `dev/docs/tests/test_distribution_claims.py`

## Description

- Grounded step in plan W05.P11, ADR, `dev/packaging/evidence.py` (DistributionEvidence schema), `dev/release/readiness.py` (REQUIRED_DISTRIBUTION_ROWS), and the full docs/ tree to enumerate current acquisition claims.
- Scanned README.md and all user-facing docs Markdown files; confirmed current docs make no positive acquisition channel claims — all channels are explicitly disclaimed as unavailable.
- Identified `docs/_release_notes_template.md` as the sole file matching a pip-install pattern; determined it is a Sphinx-orphan internal template (not a user-facing page) and excluded it via the `_is_internal_path` filter.
- Authored `dev/docs/tests/test_distribution_claims.py` with seven channel-identifying patterns (pip, uvx, scoop, brew install, brew tap, Claude marketplace URL, MCPB file reference), each mapped to their required REQUIRED_DISTRIBUTION_ROWS.
- Added `_passing_evidence_rows()` helper that loads DistributionEvidence JSON files from `var/distribution-install-readiness/` without cohort binding, accepting only schema-valid records with PASSED status.
- Added `test_no_unevidenced_channel_claims()`: returns early when no claims are found; otherwise fails with an instructive per-file message naming the claim and all missing evidence rows.
- Added `test_claim_row_ids_are_in_required_distribution_rows()`: guards against typos in the pattern mapping.
- Diagnosed and fixed xdist worker crash: conftest enforces exactly one `hex_*` marker per test; added `pytest.mark.hex_core` to `pytestmark`.
- Ran ruff check, ruff format --check, ty check — all clean.
- Ran both tests under xdist: 2 passed.
- Committed as `df3fbcc4e1` with explicit pathspec.

## Outcome

Gate lands green: current docs make no positive acquisition channel claims, so both tests pass with zero evidence required. The gate is fail-closed: any doc update advertising a channel before its `var/distribution-install-readiness/` evidence lands will produce an instructive failure naming the doc file, the matched claim, and all missing distribution rows.

Current claim-vs-evidence red list: none. All seven patterns return zero matches across 58 scanned Markdown files (README.md + docs/**/*.md excluding Sphinx-internal paths).

## Notes

Design choice: dynamic scan rather than a curated claims registry file. The current docs have no acquisition claims so the dynamic approach lands green without needing a registry. The `_is_internal_path` guard (exclude any path component starting with `_`) cleanly handles `_release_notes_template.md` which contains a pip-install checklist item in an internal release template.
