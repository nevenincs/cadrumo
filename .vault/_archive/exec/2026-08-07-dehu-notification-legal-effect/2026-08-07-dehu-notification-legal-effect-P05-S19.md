---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:06cc71a6f5ef14f05484764925f2864164189b54b19b0658807655c089da294a'
step_id: 'S19'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---
# Reproduce the production custody regression through a real isolated create setup-interruption process-restart and login lifecycle using the file backend and original passphrase, then identify the first commit and invariant that permits encrypted bucket state to outlive its only master-key route.

## Scope

- `src/cadrumo/application/user_profile`
- `src/cadrumo/adapters/persistence/storage/master_key`
- `src/cadrumo/entrypoints/cli/_config`

## Description

- Run a fresh-process file-custody lifecycle in isolated storage with a synthetic passphrase.
- Create a profile through the production CLI and verify the two file-custody artefacts exist.
- Refuse an incomplete quiet setup through the production CLI, then verify both artefacts remain.
- Register a real credential-first `setup_incomplete` profile in a separate process, then run fresh-process profile listing, logout, and login through the production CLI.
- Inspect the configured production store by presence and metadata only; inspect keyring availability and material presence without serialising values.
- Trace create, login, file fallback, reset, and reclaim ownership through the application and storage modules.
- Compare the credential-first registration and AUTO-provider history to identify the first broken invariant.

## Outcome

The isolated file backend retained `master.key` and `master.kdf` across full CLI creation, a deliberate setup refusal, a credential-first `setup_incomplete` registration, process restart, logout, and login with the same synthetic passphrase. The ordinary incomplete or refused lifecycle therefore does not delete file custody material.

The configured production metadata contains encrypted profile state and wrapped bucket DEKs while both file-master artefacts are absent. The configured AUTO keyring probe is available, but a safe material-presence read fails with an unavailable-keyring classification caused by Windows error 1312; AUTO then selects the empty file backend. Reset deletes bucket-scoped data only, and storage reclaim excludes durable secrets, so neither path explains the absent file material.

Commit `70a493bc66` introduced credential-first registration and its claim that the supplied passphrase protects the new bucket. It forwards a passphrase callback into `profile_create_storage_span`, but `get_master_key_provider` documents and implements that callback for the file backend only. With AUTO and a usable keyring, registration can establish keyring custody without persisting backend authority; a later keyring-read failure routes to the empty file store. That violates the required invariant: an encrypted bucket must retain one durable, discoverable master-key authority across process restart and backend availability changes.

No production profile, secret-store, keyring value, bucket identity, or ciphertext was modified. No code change was made in this Step.

## Notes

The focused existing real-subprocess custody test is stale against the current required profile flags and was deselected by the default unit marker; its failure was not used as evidence. The independently run isolated lifecycle supplied the current minimum flag set and passed every asserted stage.
