---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:9680334b79d1a118e0b7aec3acadec5870fc126fedde4140938ac08f7ea96552'
step_id: 'S89'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the eight fixed file leaves directly under a declared category using the now-landed StoragePathDefinition grammar mechanism, the same shape blob_manifest and the bucket layout already use, rather than StorageNodeKind.FILE taxonomy members: the five secret-store files master.key, master.kdf, master.lock, keyring.lock in master_key/_master_key.py and master.recovery.key in user_profile/_custody.py, none yet covered by the mechanism though secret_index sits in the same file already, plus cache/corpus-search/corpus.sqlite, cache/corpus-text/cadrumo_corpus_text_cache.json, and logs/cadrumo.log

## Scope

- `src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`
- `src/cadrumo/application/user_profile/_custody.py`

## Description

- Declare the five fixed file leaves directly under the secret store as taxonomy members: `master.key`, `master.kdf`, `master.lock`, `keyring.lock`, `master.recovery.key`.

## Outcome

Landed as "feat(storage): declare the secret store's five file leaves and gate directory-grammar drift." Five new `StorageCategory` members (`SECRETS_MASTER_KEY`, `SECRETS_MASTER_KDF`, `SECRETS_MASTER_LOCK`, `SECRETS_KEYRING_LOCK`, `SECRETS_MASTER_RECOVERY_KEY`), each `StorageNodeKind.FILE`, `override_policy=FIXED`, `consumer_module` naming `_master_key.py`/`_custody.py`. The `secret_index` `StoragePathDefinition` grammar (Family 1's sixth file, already declared) was re-anchored in the same commit. A new directory-grammar agreement gate lands with two positive controls.

**A deliberate, non-obvious constraint, captured here verbatim from source rather than paraphrased, because "simplify this into a `storage_path()` call" is exactly what a future reader will attempt**: these five members carry no `settings_field` and are **not** resolvable via `storage_path()`. `SECRETS` (the parent category) is `StorageOverridePolicy.OPERATOR_OVERRIDABLE`; composing root + this literal subpath would silently disagree with the real location whenever an operator overrides `cadrumo_secret_store_dir` away from its default — writing key material to the wrong place relative to where the operator redirected. The producers' existing resolution is unchanged: each consumer keeps resolving through the settings field / `self._store_dir` it already reads (which honours the override correctly) and cross-references only the bare filename off these members.

## Notes

Verified independently against committed HEAD (`c16bb9a0ae`): all five members present in `_storage_taxonomy.py`, `secret_index` grammar present in `_storage_path_definitions.py`, the override-policy reasoning above quoted from the source comment rather than reconstructed from memory. This closes the item flagged in the closure-statement reference as "the area that has surfaced three separate ways" — independent manual review, the audit's taint pass, and this declaration all converged on the same five files.
