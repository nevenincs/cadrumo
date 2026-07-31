---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:73e7d3634da2ee65fedb9bb43ef5bc1c8dbad0074ef2a114d8576785c20fc468'
step_id: 'S02'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Read the verdict at authority load so a fingerprint match constructs with validation marked done and skips validate_registry, persist a fresh verdict after a green validate_registry, and delete the verdict then re-validate on any mismatch

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`

## Description

- Compute the verdict key in `_load_authority` from the exact `(registry-tree + convenio, source-evidence)` fingerprint tuples the `lru_cache` already keys on, plus the package version.
- On a certified match (`registry_validation_is_certified`), construct the authority with validation marked done via a new `_mark_registry_validated` method, skipping `validate_registry` entirely (including the `modelo list` path, which routes through the same authority).
- On a miss, run `validate_registry` as before and then `certify_registry_validation` to persist a fresh green verdict.
- Refactor `validate_registry` to share `_mark_registry_validated`, so the direct-validation and verdict-skip paths reach identical validated state.
- Rely on the existing mismatch semantics in the verdict helpers: a stored key that no longer matches the current fingerprints is deleted and the tree re-validates and rewrites.

## Outcome

The authority now reads a persisted green verdict at load and skips runtime re-validation on a fingerprint match. An in-process probe against the bundled tree under an isolated storage root measured the cold path (no verdict) at 12.03s and the warm path (verdict present, caches cleared) at 1.01s, a ~11s saving that eliminates the first-touch validation cliff; one verdict file was written on the cold run and consumed on the warm run.

`ruff check`, `ruff format --check`, and `ty check` are clean on the touched module. The full registry test suite is green on the authority surface: 2987 passed. Two failures in the run are peer-owned and outside this Step's surface (`_validate_evidence.py` broad-exception hygiene and an absolute-private-import in the corpus freshness test), both landed by the parallel P02 commits `10ad52df0e` (S06) and `33c58b2a63` (S07); `_validate_evidence.py` is unmodified in this Step.

## Notes

Test isolation holds without change: the pytest storage root is a per-pid temp directory, so verdict files never touch the worktree, and the `_load_authority` lru cache already dedupes the bundled load per session, so the verdict is consulted once per unique tree per process. A stale shipped verdict is safe by construction (its key will not match a drifted fingerprint, so it misses and the tree re-validates). The ship-in-wheel first-touch variant (S03) must reckon with mtime-based fingerprints not surviving packaging; that is resolved and documented in the S03 record. No incidents; no scaffolds left in code. The two peer-owned P02 gate failures are reported to the coordinator, not fixed here, per the distinguish-owner discipline.
