---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:94fded5e963e10de4e533d8db09d1889edd325443479e494cb2b2ebd833d4d63'
step_id: 'S232'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Retain observability file-read retry semantics while delegating successful file-digest mechanics to core hash_file

## Scope

- `src/cadrumo/core/observability/_fingerprint.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `d0f83e66e7` delegated only the successful whole-file read to `core.hashing.sha256_file`, keeping the module's five-attempt `PermissionError` retry loop and its tree-fold / incremental accumulations, which are not whole-file reads and stay on `hashlib.sha256()` directly.

- Delegate `_file_sha256`'s successful-read path to `core.hashing.sha256_file` while retaining the five-attempt retry loop around `PermissionError`.
- Leave `_hash_tree`'s multi-entry fold and `compute_corpus_sha256`'s two-channel fold as incremental `hashlib.sha256()` accumulations, since neither is a single-file, single-shot read.

## Outcome

`src/cadrumo/core/observability/_fingerprint.py` imports `sha256_file, sha256_hex` from `..hashing` at line 20. `_file_sha256` (lines 26-38) wraps `sha256_file` in the five-attempt `PermissionError` retry loop, catching the exception, sleeping 0.05s between attempts, and re-raising on exhaustion — this control-flow retry is retained verbatim, only the successful digest call is delegated. Two residual `hashlib.sha256()` constructors remain at lines 95 and 139: line 95 folds a sorted `(relative_path, digest)` tuple stream into a tree fingerprint across a loop of `.update()` calls, and line 139 folds a settings-blob digest and an env-file digest together with domain-separator literals — both are genuinely incremental multi-`.update()` folds, not reducible one-shot bodies, so the AST recurrence gate (S235) correctly leaves them out of scope.

Verified against HEAD: the import, the retry-preserving delegation, and both residual incremental folds match the audit brief exactly.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/core/observability/tests/test_replay.py src/cadrumo/core/observability/tests/test_replay_golden.py src/cadrumo/core/observability/tests/test_golden.py` reports 34 passed (this module has no dedicated fingerprint test file; it is exercised through the replay-gating tests that consume `compute_corpus_sha256` and `_hash_tree` via `run_context` / `replay_run`).

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
