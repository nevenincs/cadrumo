---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:22d79d71e04180a7c09ca926f1b842b6c40a457116a1964e4459ac2fab8a7746'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S205` Review

## S205-001 | PASS | Evidence bundle manifests use registered secure storage

`EvidenceBundleRepository` extends `SecureBoundRepository` and declares the
registered `APPLICATION_EVIDENCE_BUNDLE_NAMESPACE` namespace, sensitivity, and
schema version. `EvidenceBundleService` resolves bucket-scoped repositories via
`secure_object_repository_for_bucket(bucket_id, settings)`, keeping production
storage routing centralized.

## S205-002 | PASS | Plain-file export is explicit and bounded

`export()` writes a ZIP only to the caller-provided `output_path`, after loading
and verifying the encrypted manifest. Existing tests prove the ZIP is outside
the runtime storage root, that `manifest.json` is written last, and that export
does not mutate secure-object rows.

## S205-003 | FIXED | Evidence errors now use localized core envelopes

Evidence bundle lookup misses and export verification refusals now raise the
registered core-derived exception classes with `translated_message` keys and
structured context. Tests assert the locale key and context rather than raw
English text.

## S205-004 | PASS | Validation

- the historical check passed.
- the historical check passed with 15 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S205
slice.

Disposition: close `AFR-103`.
