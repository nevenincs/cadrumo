---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S20'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Implement the manifest-digest cross-check over a timestamp-independent projection or correct the contract docstring

## Scope

- `src/aeat/application/bucket_maintenance/_manifest_digest.py`

## Description

- Correct the `_manifest_digest` module and function docstrings: they claimed the
  importer recomputes-and-compares the digest, which it does not and cannot (the
  manifest carries host-specific lifecycle timestamps). Document the true
  mechanism: the digest is bound into the sealed payload AEAD associated data, so
  a tampered digest fails the authentication tag and the import is refused at
  decryption.

## Outcome

Doc-vs-code contract gap closed (flagged by both the crypto and cross-machine
axes). 4 manifest-digest tests green. Committed in `ea1baea5e`.

## Notes

A literal recompute cross-check would require a timestamp-independent manifest
projection; the AEAD binding already provides authoritative integrity, so the
docstring correction is the right resolution rather than adding a redundant gate.
