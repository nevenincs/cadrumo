---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:172988f9558fafcf0595d4537be626be65456da54766dd39f82cd27add3a6126'
step_id: 'S110'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Delete the dead secret-tempfile bridge (materialise_secret, export_to_temp_path) rather than pin it with a dir= fix, confirmed zero production callers and zero dynamic reference across the tree, keeping the live secret-store factory it sat beside

## Scope

- `src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py`

## Description

- Delete the dead secret-tempfile bridge (`materialise_secret`, `export_to_temp_path`) rather than pin it with a `dir=` fix.

## Outcome

Landed as "fix(storage): delete the dead secret-tempfile bridge, keep the live factory." Confirmed dead at HEAD independently, twice: every reference across the tree is the definition, an `__all__` entry, a facade re-export, a docstring mention, or the bridge's own test — zero production callers, zero dynamic reference (no `getattr`, `import_module`, or string-keyed dispatch onto either name). Deletion chosen over pinning a `dir=` fix: an unexercised helper writing decrypted secrets to the OS tempdir, sitting in the public facade with an inviting docstring, reads as sanction to the next author who needs a path-shaped secret — the dormant-capability hazard `no-dormant-source-resolvers` codifies for resolvers, applied here to a bridge. The live secret-store factory it sat beside is untouched.

## Notes

Not a Step this reconciliation commissioned — found already landed while verifying the surrounding secret-store commits, and given its own Step retroactively so the deletion is tracked rather than surviving only as a commit message.
