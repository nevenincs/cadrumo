---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:89864ec4e54427c0de42724071bbaf1abc9b89e195be3dab4a6c4a451a01469d'
step_id: 'S01'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Add a validation-verdict record keyed by the complete registry-tree, convenio, and source-evidence fingerprint tuples plus package version and outcome, with load, store, and delete-on-mismatch helpers using real filesystem behavior

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_verdict.py`

## Description

- Add `_validate_verdict.py`: a strict pydantic `ValidationVerdict` record (`extra="forbid"`, frozen) carrying `verdict_key`, `package_version`, and `outcome`.
- Add `compute_verdict_key` folding the complete fingerprint tuples the authority already computes (registry tree plus convenio, and the source-evidence set) plus the package version into one SHA-256, with a per-group label so a tuple cannot collide across groups.
- Add `verdict_cache_path` deriving the writable per-storage-root location from a new settings field, filename hashed on the resolved root path so distinct registry roots never share a file while a fingerprint change on one root rewrites in place.
- Add `bundled_verdict_path` returning the read-only shipped location as a sibling of the bundled tree (never inside the fingerprinted tree it certifies), and `None` for any mutable authoring tree.
- Add `read_verdict` (strict-parse, `None` on absent/unreadable/foreign), `write_verdict` (atomic sibling-temp plus `os.replace`), and best-effort `delete_verdict`.
- Add `registry_validation_is_certified` (writable verdict first with delete-on-mismatch, then the read-only shipped verdict) and `certify_registry_validation` (persist a fresh green verdict).
- Add the `cadrumo_validation_verdict_cache_dir` settings field and its `cache/registry-verdict` state-root derivation; classify it unbounded-by-design in the settings lifecycle gate.
- Add real-filesystem helper tests: location derivation, distinct-root files, sibling shipped path, roundtrip, foreign-file tolerance, certify-then-match, and delete-on-mismatch.

## Outcome

Landed the verdict record and its load/store/delete-on-mismatch helpers plus the settings surface. `ruff check`, `ruff format --check`, and `ty check` clean on the touched files. `test_validation_verdict_location.py` (10 helper tests), the settings lifecycle and state-root gates, and the registry reviewability line-budget gate all pass; the new `_validate_verdict.py` stays well under the 300-line `_validate*.py` reviewability ceiling. Registry collection is clean.

The authority read/skip wiring (S02), the release-build stamp (S03), and the authority-integration regression pin (S04) build on these helpers.

## Notes

The verdict is derived and rebuildable: a key mismatch or a foreign record deletes the writable verdict and forces a full re-validation, with no migration path per no-legacy-compatibility. The shipped verdict is deliberately a sibling of the registry root so its own presence never perturbs the fingerprint it certifies. No incidents; no scaffolds left in code.
