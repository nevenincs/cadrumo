---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:63b86700ca51fd42a076433f43f6b68db0039131555582703271c529b561d6cb'
step_id: 'S90'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate review-package recipient fingerprints to core sha256_hex

## Scope

- `src/cadrumo/application/modelo/_review_package_recipient_registry.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `604c8dce53` routed sixteen production one-shot SHA-256 bodies through `core.hashing.sha256_hex`, including this module.

- Route the review-package recipient fingerprint construction through `core.hashing.sha256_hex` instead of an inline `hashlib.sha256(...).hexdigest()` body.
- Preserve the argument expression unchanged so the digest bytes are identical by construction, since `sha256_hex` is `hashlib.sha256(data).hexdigest()` verbatim.

## Outcome

`src/cadrumo/application/modelo/_review_package_recipient_registry.py` imports `sha256_hex` from `...core.hashing` at line 62 and calls it at line 108 to build the recipient fingerprint. No inline `hashlib.sha256` construction remains in the module.

Verified against HEAD: the import and call site match the commit's stated scope, and the sibling Step S91 proof (`test_review_package_recipient_registry.py`) exercises the delegated fingerprint against known vectors and an encrypted registry roundtrip.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/application/modelo/tests/test_review_package_recipient_registry.py` reports 13 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
