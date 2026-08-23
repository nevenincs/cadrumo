---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:7723bb3a49def78321876f919ac3e126a5283cd794986d620c733149956cdadc'
step_id: 'S165'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# prove complete acquisition-cost fields survive the encrypted inventory repository round trip

## Scope

- `src/cadrumo/adapters/persistence/profile/tests/test_inventory_roundtrip.py`

## Description

- Replace the legacy purchase fixture with the complete acquisition envelope and role-specific evidence established by S163 and S164.
- Prove nested equality, acquisition fingerprint, capitalized value, unit basis, inventory document version, and governed secure-object metadata after encrypted save and load.
- Mutate nine required or cross-checked acquisition axes through real decryption and re-encryption and prove strict load refusal.
- Substitute one valid evidence digest and prove strict load succeeds while the acquisition fingerprint changes.
- Scan the database and WAL for every evidence reference, digest, component identity, and distinctive financial amount.

## Outcome

The inventory repository now has a non-tautological encrypted persistence proof for the complete acquisition-cost contract. Twelve focused tests passed; Ruff, ty, and diff hygiene passed. The final independent review was clear with no findings at any severity.

## Notes

The first review requested a valid digest-substitution proof, a missing-digest refusal, direct hashed object-key identity, and complete ciphertext-canary coverage. All were added and the same reviewer returned a clear verdict. No repository implementation defect was found and no production code changed.
