---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S91'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove recipient fingerprints against known vectors and encrypted registry roundtrip

## Scope

- `src/cadrumo/application/modelo/tests/test_review_package_recipient_registry.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `604c8dce53` added the proof against oracles outside `core.hashing` in the same change that delegated the recipient-fingerprint construction (S90).

- Prove the delegated fingerprint construction against known SHA-256 vectors independent of `core.hashing` itself (a 32-byte all-zero key and a 32-byte sequential-byte key, each with its literal SHA-256 hex digest).
- Prove the fingerprint survives an encrypted registry save-then-load roundtrip unchanged.

## Outcome

`test_review_package_recipient_registry.py` carries the literal known-vector digests `_KNOWN_VECTOR_ZERO32_SHA256` / `_KNOWN_VECTOR_SEQ32_SHA256` (lines 75, 80) parametrized against `test_known_vector_fingerprint_survives_the_encrypted_registry_roundtrip`, so the assertion is checked against a value not derived from the `sha256_hex` call under test, combined with a real encrypted-registry roundtrip rather than a test double.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/application/modelo/tests/test_review_package_recipient_registry.py` reports 13 passed.

## Notes

This record was authored after the proof had already landed; it documents the verified state rather than performing new implementation work. The test file exercises the real encrypted registry rather than a test double, per the project's no-mocks-in-integration-tests discipline.
