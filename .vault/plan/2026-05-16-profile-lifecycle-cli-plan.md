---
tags:
  - '#plan'
  - '#profile-lifecycle-cli'
date: '2026-05-16'
modified: '2026-05-16'
tier: L2
related:
  - '[[2026-06-03-profile-lifecycle-cli-cascade-supersession-adr]]'
  - '[[2026-06-04-profile-lifecycle-cli-research]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
---


# `profile-lifecycle-cli` plan

### Phase `P01` - typed identity primitives (DONE)

P01 closed in commit `5fe2e2ca` with `ProfileName` and `BucketId`
aliases under `src/aeat/domain/profile/_constants.py` and
`src/aeat/domain/buckets/_constants.py` (promoted from a
module-private `_BucketId`). All P01 steps below remain in the
plan body for historical traceability; the literal-`"default"`
sweep (S05 - S09) was deferred into P02 because removing the
literal without the foundation-replacement breaks callers.

- [x] `P01.S01` - `ProfileName` typed alias; `src/aeat/domain/profile/_constants.py`.
- [x] `P01.S02` - `BucketId` typed alias; `src/aeat/domain/buckets/_constants.py`.
- [x] `P01.S03` - export from profile package; `src/aeat/domain/profile/__init__.py`.
- [x] `P01.S04` - export from buckets package; `src/aeat/domain/buckets/__init__.py`.
- [x] `P01.S10` - validation tests; `src/aeat/domain/profile/test_constants.py`.
- [x] `P01.S11` - bucket-id parity tests; `src/aeat/domain/profile/test_constants.py`.

### Phase `P02` - cut the active-profile resolution over to the shipped pointer file

The plaintext pointer file IO at
`src/aeat/application/workflow/_bucket_pointer_io.py` is already
shipped (atomic write-then-rename, roundtrip tests). The
`BucketPointer` model is already shipped at
`src/aeat/application/workflow/_bucket_pointer.py`. Neither is
read by the active-profile resolution path today; the path still
reads `WorkflowState.active_profile` inside the encrypted state
row. This phase wires the existing infrastructure into the live
path, renames `active-bucket` to `active-profile` in the file
constant, removes the zombie settings field, and deletes
`WorkflowState.active_profile` with every consumer updated in the
same commit window.

- [x] `P02.S12` - rename the pointer filename constant from `active-bucket` to `active-profile`; `src/aeat/application/workflow/_bucket_pointer_io.py`.
- [x] `P02.S13` - extend `active_bucket_id_or_raise` to consult `--profile` flag, `AEAT_ACTIVE_PROFILE` env var, then pointer file via `read_pointer`, before falling back to `WorkflowState`; `src/aeat/application/workflow/_models.py`.
- [x] `P02.S14` - update every caller of `active_profile_bucket_id` / `active_profile_record` to flow through the new precedence chain; `src/aeat/entrypoints/cli/_common.py`.
- [x] `P02.S15` - update `register_active_profile` and `select_profile` to write the pointer file via `write_pointer`; `src/aeat/application/user_profile/_orchestration.py`.
- [x] `P02.S16` - delete the zombie `aeat_default_profile_name` field; `src/aeat/core/config.py`.
- [x] `P02.S17` - delete `WorkflowState.active_profile` field and the `active_profile_record` / `active_profile_bucket_id` properties; `src/aeat/application/workflow/_models.py`.
- [x] `P02.S18` - delete the `"default"` literal fall-through in the wizard; `src/aeat/application/wizard/_commands.py`.
- [x] `P02.S19` - call `provision_bucket_directory` and `write_manifest` from `initialize_workspace` so profile creation provisions the per-bucket directory tree atomically; `src/aeat/application/setup/_service.py`.
- [x] `P02.S20` - thread per-bucket SQLite URL through `create_engine_from_settings` from the resolved `BucketPaths.db_dir`; `src/aeat/adapters/persistence/storage/sql/_engine.py`.
- [x] `P02.S21` - wire the local blob-store factory to read its root from `BucketPaths.blobs_dir`; `src/aeat/adapters/outbound/storage/_factory.py`.
- [x] `P02.S22` - add the startup guard that raises `LegacyLayoutDetectedError` when `<aeat-root>/var/` exists and `<aeat-root>/buckets/` does not; `src/aeat/application/_bootstrap.py`.
- [x] `P02.S23` - precedence-chain test (flag wins over env, env wins over pointer, pointer wins over absence); `src/aeat/application/workflow/test_active_profile_resolution.py`.
- [x] `P02.S24` - regression test asserting the pointer-file integration writes on profile create; `src/aeat/application/user_profile/test_orchestration_pointer.py`.
- [x] `P02.S25` - regression test asserting `initialize_workspace` provisions the bucket directory tree and writes the manifest; `src/aeat/application/setup/test_service_provisions_bucket.py`.
- [x] `P02.S26` - legacy-layout refusal test (run startup against a synthesised legacy `var/` tree, assert `LegacyLayoutDetectedError`); `src/aeat/application/test_bootstrap_legacy_refusal.py`.

### Phase `P03` - rewire the live crypto path through `BucketSession`

`BucketSession` is fully shipped at
`src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`
with instance-scoped `_kek_buffer` / `_dek_buffer`, idle-timeout,
zeroising close, and an AST guard test asserting zero ClassVar
state. It is not wired into the production decrypt path: today
`src/aeat/adapters/persistence/storage/sql/_encrypted_columns.py`
calls `get_master_key_provider().get_master_key()` directly,
caching the master key in `ClassVar` buffers inside
`KeyringMasterKeyProvider` and `FileFallbackMasterKeyProvider`.
Two parallel chains coexist. This phase removes the ClassVar
chain and routes the live decrypt path through `BucketSession`.

- [x] `P03.S27` - rewire `_resolve_master_key` to read from the active `BucketSession` instead of `get_master_key_provider().get_master_key()`; `src/aeat/adapters/persistence/storage/sql/_encrypted_columns.py`.
- [x] `P03.S28` - delete the `_lock` / `_cache` `ClassVar`s from `KeyringMasterKeyProvider`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `P03.S29` - delete the `_lock` / `_cached_passphrase` / `_cached_master_key` `ClassVar`s from `FileFallbackMasterKeyProvider`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `P03.S30` - delete the `_purge_caches_at_exit` atexit hook now that the ClassVar caches are gone; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `P03.S31` - register an atexit hook that closes any open `BucketSession`; `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`.
- [x] `P03.S32` - regression test asserting `_encrypted_columns` decrypt path reads through `BucketSession`; `src/aeat/adapters/persistence/storage/sql/test_encrypted_columns_session.py`.
- [x] `P03.S33` - AST-guard test asserting `KeyringMasterKeyProvider` and `FileFallbackMasterKeyProvider` carry zero `ClassVar` state; `src/aeat/adapters/persistence/storage/master_key/test_master_key_no_classvars.py`.

### Phase `P04` - persistence-boundary drift fixes (five still-live findings)

The sixth finding (manifest / SQL row write-order atomicity) is
already resolved - the manifest layer no longer exists; profile
creation is a single atomic state-repository update. Five remain.

- [x] `P04.S34` - remove the `dict[str, object]` union arm from `WorkflowState.invoice_reviews`; `src/aeat/application/workflow/_models.py`.
- [x] `P04.S35` - remove the `dict[str, object]` union arm from `WorkflowState.ledger_reviews`; `src/aeat/application/workflow/_models.py`.
- [x] `P04.S36` - add public `iter_records()` to the user-profile repository and replace the private `_objects` access in `_iter_profiles`; `src/aeat/application/user_profile/_repository.py`.
- [x] `P04.S37` - replace the private access call site; `src/aeat/application/user_profile/_lifecycle.py`.
- [x] `P04.S38` - anti-tautology probe test (save profile, mutate encrypted payload, reload, assert `ValidationError` or strict inequality); `src/aeat/application/user_profile/test_repository_anti_tautology.py`.
- [x] `P04.S39` - extend the existing `WorkflowState` roundtrip to populate `invoice_reviews` and `ledger_reviews` with non-default values; `src/aeat/application/workflow/test_state_persistence_roundtrip.py`.

### Phase `P05` - rename existing CLI verbs to plain English (single-cut)

Five existing verbs rename to their operator-friendly forms. Each
rename is a single commit deleting the old name and landing the
new name. No aliases, no shims. The wizard backend
(`build_wizard_command`) is reused under the new verb names; only
the Typer registration changes.

- [x] `P05.S40` - rename `aeat config init` to `aeat config profile create NAME`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P05.S41` - rename `aeat config profile use` to `switch`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P05.S42` - rename `aeat config profile remove` to `delete`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P05.S43` - merge `view` and `status` into one `show` verb that defaults to the active profile and emits a readiness header; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P05.S44` - delete `validate` and `preflight` verbs; `their schema-validation surface folds into `show`'s readiness header; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P05.S45` - delete `get` / `set` / `unset` verbs from the operator CLI; `they re-home under `python -m aeat.diagnostics`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P05.S46` - rewrite the top-level `_config_help` summary to advertise every operator profile verb; `src/aeat/entrypoints/cli/_config/__init__.py`.

### Phase `P06` - add the genuinely missing operator verbs

Four verbs (`rename`, `edit`, `export`, `import`, `logout`) and
the three absent typed errors are genuinely new. The domain type
`UserProfilePortableExport` already exists at
`src/aeat/domain/user_profile/_values.py`; the export verb wires
it. `duplicate` collapses into `create --copy-from`.

- [x] `P06.S47` - add `BootstrapAlreadyCompleteError` typed error and register it; `src/aeat/application/workflow/_errors.py`.
- [x] `P06.S48` - add `ProfileNameCollisionError` typed error and register it; `src/aeat/application/workflow/_errors.py`.
- [x] `P06.S49` - add `ProfileLockedError` typed error and register it; `src/aeat/application/workflow/_errors.py`.
- [x] `P06.S50` - add `rename(profile_id, new_name)` to the lifecycle service; `src/aeat/application/user_profile/_lifecycle.py`.
- [x] `P06.S51` - add `aeat config profile rename NAME NEW` Typer verb; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P06.S52` - add `aeat config profile edit [NAME]` Typer verb that re-runs the wizard against an existing record; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P06.S53` - add `export(profile_id) -> UserProfilePortableExport` plus archive sealer to the lifecycle service; `src/aeat/application/user_profile/_lifecycle.py`.
- [x] `P06.S54` - add `import_archive(path) -> ProfileId` plus archive validator to the lifecycle service; `src/aeat/application/user_profile/_lifecycle.py`.
- [x] `P06.S55` - add `aeat config profile export [NAME] --to FILE` and `aeat config profile import FILE` Typer verbs; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P06.S56` - add `aeat config profile logout` Typer verb that closes the active `BucketSession`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P06.S57` - replace `duplicate` Typer verb with `create --copy-from NAME` flag landing in the same commit as `duplicate` deletes; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P06.S58` - tests for rename / edit / export / import / logout / copy-from happy paths and refusals; `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`.

### Phase `P07` - google adapter cleanup and locale regeneration

TODO: Phase intent paragraph required by the convention ADR.

- [x] `P07.S59` - remove the `profile_override` parameter from `resolve_active_profile`; `src/aeat/adapters/outbound/google/_profile_binding.py`.
- [x] `P07.S60` - remove the `--profile` flag from every `aeat config google` verb; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `P07.S61` - run the locale scaffold + audit across es/en/ca/hu for every renamed string; `src/aeat/locales`.

### Phase `P08` - diagnostics entrypoint and full gate

TODO: Phase intent paragraph required by the convention ADR.

- [x] `P08.S62` - delete the `aeat config repair list NAMESPACE` operator verb; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P08.S63` - add `python -m aeat.diagnostics` module entrypoint with `profile get / set / unset / activity` and `secure-objects list` subcommands; `src/aeat/diagnostics/__main__.py`.
- [x] `P08.S64` - smoke tests for the diagnostics entrypoint; `src/aeat/diagnostics/test_diagnostics.py`.
- [x] `P08.S65` - run the full pytest suite and resolve every failure; `src/aeat`.
- [x] `P08.S66` - run `ruff check` and resolve every diagnostic; `src/aeat`.
- [x] `P08.S67` - run `mypy` and resolve every diagnostic; `src/aeat`.
- [x] `P08.S68` - run the vault audit and confirm no new errors; `.vault`.
- [x] `P08.S69` - run a manual operator smoke against a fresh root and capture the transcript; `.vault/exec/2026-05-16-profile-lifecycle-cli`.
