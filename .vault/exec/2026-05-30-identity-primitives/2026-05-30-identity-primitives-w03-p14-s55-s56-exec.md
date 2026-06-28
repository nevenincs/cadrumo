---
step_id: S55
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W03.P14.S55-S56 — factor retained fingerprint shape duplications

## Scope

Factor the retained sha-256 hex-64 `Field(...)` literal repeated
across two modules to a single module-local shape kwargs mapping
per ADR Rule 7. The fields stay bare-str (fingerprints, not
identities) and are not promoted to identity aliases; the
duplication of the shape literal is what collapses.

## Outcome

`src/aeat/application/user_profile/__init__.py`:
- New module-local
  `_PROFILE_SNAPSHOT_HASH_KWARGS: dict[str, object] = {
  "min_length": 64, "max_length": 64,
  "pattern": r"^[0-9a-f]{64}$"}`.
- `ProfileSnapshot.canonical_hash`,
  `ProfileStaleCheckReport.stored_hash`,
  `ProfileStaleCheckReport.current_hash` all consume
  `Field(**_PROFILE_SNAPSHOT_HASH_KWARGS)`.

`src/aeat/core/corpus_manifest/__init__.py`:
- New module-local `_CORPUS_SHA256_KWARGS` with the same shape.
- `CorpusEntry.sha256` and `CorpusManifest.manifest_sha256` both
  consume `Field(**_CORPUS_SHA256_KWARGS)`.

The kwargs-mapping form (rather than a single shared `Field()`
instance) is required because pydantic `FieldInfo` is not safely
reusable across multiple fields on multiple models.

## Verification

- Probed `ProfileSnapshot` and `ProfileStaleCheckReport`
  construction with hex-64 values (succeeds) and a non-hex value
  (raises `ValidationError`).
- `uv run --no-sync pytest src/aeat/core/corpus_manifest/` returns
  `9 passed`.

## Plan steps closed

`W03.P14.S55`, `S56`.
