---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-24'
modified: '2026-07-25'
step_id: 'S41'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Thread constructor secret_store: SecretStore|None=None dependency-injection through the secret-store factory, certificate-secret backend, certificate-sources check, and materialisation helpers

## Scope

- `delete override_secret_store`
- `the module-global _override_store`
- `its if-override branch`
- `and both blob_store and storage __init__ facade exports`
- `migrate the four consuming tests to pass an EphemeralMasterKeyProvider-backed SecretStore explicitly`
- `in one atomic relocation commit including apidocs scaffold`
- `src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py`

## Description

- Delete the process-wide `override_secret_store` test helper, the `_override_store` module global, and the override branch inside `get_secret_store`.
- Remove the symbol from both the blob-store and storage facade exports.
- Migrate the materialisation tests onto the existing `store=` parameter, passing the dependency explicitly.
- Migrate the certificate-secret backend, certificate-sources check, and certificate CLI tests to resolve through the real active bucket session they already open.
- Land the deletion and every consumer migration in one atomic commit.

## Outcome

The secret store is reached through real dependency injection: the sanctioned `store=` parameter for direct callers, and the real active bucket session for the tests that already open one. No new parameter, no relocation, and no context variable were introduced, because the injection point already existed and only the override seam was masking it.

The seam had zero production callers; all four consumers were test-only. Deleting it removes a process-wide mutable global from a credential-custody path, where a leaked override between tests would have crossed secret-store boundaries silently.

The landing commit is `009ed60006`, tagged `relocation:override_secret_store`, which removed 289 lines against 178 added across seven files. The sibling step's recurrence gate, committed separately at `7305fd3ae2`, now structurally bars the override-seam shape from returning to production.

## Notes

The originating step row is malformed: its action text carries embedded semicolons, which the record scaffolder reads as scope-entry separators. The scope block above therefore lists fragments of the action sentence as if they were file paths, when the single real scope file is the materialisation module named last. The row is left as authored rather than hand-corrected, because plan rows are owned by the plan verbs and a hand edit would bypass their identifier guarantees. The corruption is cosmetic to this record and does not affect the step's canonical identifier.

One consuming test module, the certificate-sources check, was migrated concurrently by another agent using an identical approach. Its staged diff carried only the seam migration, so it was included here to keep the deletion atomic; it is a consumer of the deleted symbol rather than unrelated peer-campaign work.

This record was authored on 2026-07-24, after the work landed. It was the sole execution-record gap in this plan that the originating rescope record does not answer: every sibling step from S22 onward already carries a record, and S01 through S21 are the carried-forward backend steps that record explicitly attributes to the originating campaign stem.
