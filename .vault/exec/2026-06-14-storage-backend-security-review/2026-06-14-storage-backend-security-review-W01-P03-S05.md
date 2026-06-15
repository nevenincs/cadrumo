---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S05'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Apply the manifest KDF validation window to the file-fallback parameters on read and reject below-floor Argon2 cost

## Scope

- `src/aeat/adapters/persistence/storage/master_key/_master_key_records.py`

## Description

- Add the OWASP-baseline Argon2 cost window (`ge`/`le` on `memory_cost`,
  `time_cost`, `parallelism`) to the file-fallback `_KdfParameters`, reusing the
  canonical bound constants from `_kdf_params` rather than re-declaring literals.

## Outcome

A tampered or buggy `master.kdf` declaring a below-floor cost is refused on read as
`MasterKeyUnavailableError` instead of deriving a weakened KEK. Proven by a new
real-behavior test that provisions a store, lowers `memory_cost` to 8, and asserts
the refusal on `get_master_key`. Storage tree collect-only clean (no import cycle
from the new intra-package import). Committed in `e6f280e68`.

## Notes

The baseline mint constants equal the floor exactly (19 MiB / 2 / 1), so minting
still validates.
