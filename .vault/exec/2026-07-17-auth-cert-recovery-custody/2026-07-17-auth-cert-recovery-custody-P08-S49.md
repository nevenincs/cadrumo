---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:dd749b5c87bd76f6cc706de7d452197c7b036018739a44990e9213cd04bcecf9'
step_id: 'S49'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Convert recovery-key, mnemonic, unwrapped master-key, and enrollment-time DEK material from immutable bytes and str to wipeable mutable buffers so the substrate zeroise primitive can reach them, closing the plaintext-DEK exposure window that the P04 door safety review found is structurally wider here than on the BucketSession steady-state path because it opens on every recovery mint, unwrap, and passphrase change, deferred by that review as a pre-existing disclosed project-wide Python immutability limitation rather than a new regression, and tracked here so a later pass over this surface cannot re-introduce it as a false already-covered assumption

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`

## Description

## Outcome

## Notes
