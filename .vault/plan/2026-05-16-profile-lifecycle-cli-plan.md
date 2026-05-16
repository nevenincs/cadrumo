---
tags:
  - '#plan'
  - '#profile-lifecycle-cli'
date: '2026-05-16'
tier: L2
related:
  - '[[2026-05-16-profile-lifecycle-cli-adr]]'
  - '[[2026-05-16-profile-lifecycle-cli-research]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `profile-lifecycle-cli` plan

### Phase `P01` - typed identity primitives and `"default"` retirement

Introduce the typed primitives downstream phases will use and
delete the hard-coded `"default"` profile name. There is no
`DEFAULT_PROFILE_NAME` constant - `create NAME` always requires
an operator-typed name, so the literal disappears entirely.

- [x] `P01.S01` - create the `ProfileName` typed alias with kebab-case validation; `src/aeat/domain/profile/_constants.py`.
- [x] `P01.S02` - create the `BucketId` typed alias (internal storage-layer identifier, never operator-facing); `src/aeat/domain/bucket/_constants.py`.
- [x] `P01.S03` - export the new profile module from the domain package; `src/aeat/domain/profile/__init__.py`.
- [x] `P01.S04` - export the new bucket module from the domain package; `src/aeat/domain/bucket/__init__.py`.
- [ ] `P01.S05` - delete the `"default"` literal in the wizard command builder; `src/aeat/application/wizard/_commands.py`.
- [ ] `P01.S06` - delete the `"default"` literal in the wizard persistence handler; `src/aeat/application/wizard/_persistence.py`.
- [ ] `P01.S07` - delete the `"default"` literal in the workflow-state default factory; `src/aeat/application/workflow/_models.py`.
- [ ] `P01.S08` - delete the `"default"` literal in the setup service bootstrap; `src/aeat/application/setup/_service.py`.
- [ ] `P01.S09` - sweep and delete remaining `"default"` profile-name literal callers; `src/aeat`.
- [x] `P01.S10` - add unit tests asserting `ProfileName` rejects empty, whitespace, and non-kebab inputs; `src/aeat/domain/profile/test_constants.py`.
- [x] `P01.S11` - add unit tests asserting `BucketId` rejects empty, whitespace, and non-kebab inputs; `src/aeat/domain/bucket/test_constants.py`.

### Phase `P02` - storage layout foundation

Land the May-14 ADR's per-profile directory layout, the plaintext
active-profile pointer file with precedence chain, and the legacy
`var/` refusal. No CLI surface change in this phase; the
foundation must hold before the operator verbs wire onto it.

- [ ] `P02.S12` - rename `ProfileBucketPointer` to `BucketPointer` and collapse the `profile_id` / `bucket_id` aliasing; `src/aeat/application/workflow/_models.py`.
- [ ] `P02.S13` - delete `WorkflowState.active_profile` field; `src/aeat/application/workflow/_models.py`.
- [ ] `P02.S14` - delete `Settings.aeat_default_profile_name`; `src/aeat/application/_settings.py`.
- [ ] `P02.S15` - introduce the `<aeat-root>/active-profile` plaintext pointer file reader and writer; `src/aeat/application/profile/_active_pointer.py`.
- [ ] `P02.S16` - implement the active-profile precedence chain (`--profile` flag, `AEAT_ACTIVE_PROFILE` env, pointer file); `src/aeat/application/profile/_active_pointer.py`.
- [ ] `P02.S17` - introduce `NoActiveProfileError` typed error with operator-facing message; `src/aeat/application/profile/_errors.py`.
- [ ] `P02.S18` - introduce `LegacyLayoutDetectedError` typed error refusing legacy `var/` on startup; `src/aeat/application/profile/_errors.py`.
- [ ] `P02.S19` - register the new error codes in the central registry; `src/aeat/core/errors/_registry.py`.
- [ ] `P02.S20` - provision per-profile directory layout under `<aeat-root>/buckets/<bucket-id>/{db,blobs,audit}/` in the lifecycle service; `src/aeat/application/setup/_service.py`.
- [ ] `P02.S21` - add the legacy-layout refusal check on startup; `src/aeat/application/_bootstrap.py`.
- [ ] `P02.S22` - add tests for the active-profile precedence chain across all three sources; `src/aeat/application/profile/test_active_pointer.py`.
- [ ] `P02.S23` - add tests for the legacy-layout refusal path; `src/aeat/application/test_bootstrap_legacy_refusal.py`.

### Phase `P03` - session lifecycle and adapter re-keying

Replace ClassVar caches with the in-memory `BucketSession`,
implement explicit teardown on switch / logout / exit, and re-key
every auth and google adapter that read the active profile from
removed surfaces.

- [ ] `P03.S24` - introduce the `BucketSession` object holding the KEK, SQLAlchemy engine, storage adapter providers; `src/aeat/application/profile/_session.py`.
- [ ] `P03.S25` - remove the `KeyringMasterKeyProvider._cache` ClassVar; `replace with `BucketSession`-scoped state; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P03.S26` - remove the `FileFallbackMasterKeyProvider._cached_passphrase` / `_cached_master_key` ClassVars; `replace with session-scoped state; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P03.S27` - replace the module-level SQLAlchemy engine singleton with a session-owned engine registry; `src/aeat/adapters/persistence/storage/sql/_engine.py`.
- [ ] `P03.S28` - add the per-profile filesystem lockfile acquisition / release at `<aeat-root>/buckets/<bucket-id>/.lock`; `src/aeat/application/profile/_session.py`.
- [ ] `P03.S29` - implement explicit session teardown on switch (engine close, key zeroise, adapter handle release); `src/aeat/application/profile/_session.py`.
- [ ] `P03.S30` - re-key `_acquisition_lock.py` to read the active profile from the precedence chain; `src/aeat/application/auth/_acquisition_lock.py`.
- [ ] `P03.S31` - re-key `_sessions.py` to read the active profile from the precedence chain; `src/aeat/application/auth/_sessions.py`.
- [ ] `P03.S32` - remove the `profile_override` parameter from `resolve_active_profile`; `src/aeat/adapters/outbound/google/_profile_binding.py`.
- [ ] `P03.S33` - remove the `--profile` flag from every `aeat config google` verb; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P03.S34` - rename the Google Drive mirror folder string from `aeat-vault` to `aeat-profile`; `src/aeat/adapters/outbound/google/_profile_binding.py`.
- [ ] `P03.S35` - add the session-bytes-change-on-switch property test; `src/aeat/application/profile/test_session_lifecycle.py`.
- [ ] `P03.S36` - add the per-profile lockfile contention test (second process gets `BucketBusyError`); `src/aeat/application/profile/test_session_lockfile.py`.

### Phase `P04` - persistence-boundary cleanup (the six findings)

Land the six backend findings the ADR commits to. Independent of
the CLI surface; closes the boundary on the path the new verbs
traverse.

- [ ] `P04.S37` - reorder bucket-creation writes so the SQL row commits before the manifest rename; `src/aeat/application/setup/_service.py`.
- [ ] `P04.S38` - remove the `dict[str, object]` union arm from `WorkflowState.invoice_reviews`; `src/aeat/application/workflow/_models.py`.
- [ ] `P04.S39` - remove the `dict[str, object]` union arm from `WorkflowState.ledger_reviews`; `src/aeat/application/workflow/_models.py`.
- [ ] `P04.S40` - add the public `iter_records()` method to the user-profile repository; `src/aeat/application/user_profile/_repository.py`.
- [ ] `P04.S41` - replace the private `_objects` access in `_iter_profiles` with the public iterator; `src/aeat/application/user_profile/_lifecycle.py`.
- [ ] `P04.S42` - add the anti-tautology probe test against the profile boundary; `src/aeat/application/profile/test_lifecycle_anti_tautology.py`.
- [ ] `P04.S43` - extend the `WorkflowState` roundtrip to populate `invoice_reviews` and `ledger_reviews` with non-default values; `src/aeat/application/workflow/test_persistence_roundtrip.py`.
- [ ] `P04.S44` - add the manifest / SQL row write-order atomicity test; `src/aeat/application/setup/test_service_atomicity.py`.

### Phase `P05` - profile lifecycle application service

Build the new service surface the operator CLI verbs delegate to.
Service lands before the CLI; every P06 Step wires into a tested
service.

- [ ] `P05.S45` - create the `ProfileLifecycleService` consolidating `create`, `switch`, `logout`, `edit`, `rename`, `delete`, `export`, `import`; `src/aeat/application/profile/_lifecycle.py`.
- [ ] `P05.S46` - define remaining typed errors `ProfileLockedError`, `ProfileNameCollisionError`, `ProfileNotFoundError`; `src/aeat/application/profile/_errors.py`.
- [ ] `P05.S47` - register the new error codes in the central registry; `src/aeat/core/errors/_registry.py`.
- [ ] `P05.S48` - implement `create NAME --copy-from SRC` with fresh KEK, salt, recovery mnemonic, and keystore entry; `src/aeat/application/profile/_clone.py`.
- [ ] `P05.S49` - implement `export NAME --to FILE` producing a sealed archive (ciphertext tree, manifest, recovery-wrapped key); `src/aeat/application/profile/_export.py`.
- [ ] `P05.S50` - implement `import FILE` registering an archive as a locked profile; `src/aeat/application/profile/_export.py`.
- [ ] `P05.S51` - wire bucket-event emission for `profile.created`, `profile.activated`, `profile.updated`, `profile.cloned`, `profile.renamed`, `profile.deleted`, `bucket.created`, `bucket.deleted`, `bucket.exported`, `bucket.imported`, `bucket.session.closed`; `src/aeat/application/profile/_lifecycle.py`.
- [ ] `P05.S52` - add lifecycle service tests covering create / switch / logout happy paths; `src/aeat/application/profile/test_lifecycle.py`.
- [ ] `P05.S53` - add lifecycle service tests covering edit / rename / delete; `src/aeat/application/profile/test_lifecycle.py`.
- [ ] `P05.S54` - add lifecycle service tests covering name-collision refusal on create / rename / import; `src/aeat/application/profile/test_lifecycle.py`.
- [ ] `P05.S55` - add the `--copy-from` cryptographic isolation test (fresh nonces, salts, keystore entries on target); `src/aeat/application/profile/test_clone.py`.
- [ ] `P05.S56` - add the export/import roundtrip test against a real temporary `<aeat-root>`; `src/aeat/application/profile/test_export_roundtrip.py`.

### Phase `P06` - operator CLI surface migration

Mount `aeat config profile` with the ten operator verbs, delete
the legacy `init` and `profile` subgroup wiring in the same
commits, rewrite the top-level help summary. Every cryptic verb
gone.

- [ ] `P06.S57` - mount the `aeat config profile` Typer subgroup; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S58` - wire `aeat config profile create NAME` with all wizard prompts, password prompt, and `--copy-from`; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S59` - wire `aeat config profile switch NAME` with password prompt and session teardown of previous; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S60` - wire `aeat config profile logout` closing the active session; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S61` - wire `aeat config profile list [--with-status]` reading manifests without unlock; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S62` - wire `aeat config profile show [NAME]` with default-to-active and missing-fields header; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S63` - wire `aeat config profile edit [NAME]` with default-to-active and current-value defaults; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S64` - wire `aeat config profile rename NAME NEW` updating manifest, pointer file, and keystore alias; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S65` - wire `aeat config profile delete NAME` with `--yes` plus typed-back-NAME double-confirm; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S66` - wire `aeat config profile export [NAME] --to FILE` with default-to-active; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S67` - wire `aeat config profile import FILE` registering the locked archive; `src/aeat/entrypoints/cli/_config/_profile.py`.
- [ ] `P06.S68` - delete the legacy `aeat config init` command and `build_wizard_command` mounting; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P06.S69` - delete every legacy `aeat config profile *` verb (use, view, validate, preflight, status, remove, duplicate, list, get, set, unset); `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P06.S70` - rewrite the top-level `_config_help` summary to advertise every profile verb; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P06.S71` - add the post-command next-step hint footer pointing at leaf verbs; `src/aeat/entrypoints/cli/_config/_profile.py`.

### Phase `P07` - dev-facing surface retirement

Delete the dev-shaped `aeat config repair list NAMESPACE` from
the operator CLI and land the engineer surface as a module
entrypoint.

- [ ] `P07.S72` - delete the `aeat config repair list` verb from the operator CLI; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P07.S73` - create the `aeat.diagnostics` module entrypoint; `src/aeat/diagnostics/__main__.py`.
- [ ] `P07.S74` - implement the `diagnostics secure-objects list` subcommand; `src/aeat/diagnostics/_secure_objects.py`.
- [ ] `P07.S75` - implement the `diagnostics profile get / set / unset KEY` subcommands; `src/aeat/diagnostics/_profile.py`.
- [ ] `P07.S76` - implement the `diagnostics profile activity [NAME]` subcommand reading bucket-event-history; `src/aeat/diagnostics/_profile.py`.
- [ ] `P07.S77` - add smoke tests for every diagnostics subcommand; `src/aeat/diagnostics/test_diagnostics.py`.

### Phase `P08` - locale catalogue regeneration

Re-scaffold every operator-facing string across the four
catalogues through the locale CLI. No hand edits.

- [ ] `P08.S78` - run the locale scaffold pass to surface every new and removed string; `src/aeat/locales`.
- [ ] `P08.S79` - translate the Spanish catalogue against the new operator vocabulary; `src/aeat/locales/es.yml`.
- [ ] `P08.S80` - translate the English catalogue; `src/aeat/locales/en.yml`.
- [ ] `P08.S81` - translate the Catalan catalogue; `src/aeat/locales/ca.yml`.
- [ ] `P08.S82` - translate the Hungarian catalogue; `src/aeat/locales/hu.yml`.
- [ ] `P08.S83` - run the locale audit and resolve every diagnostic; `src/aeat/locales`.

### Phase `P09` - test surface rewrite and full gate

Rewrite the lifecycle test surface against the new operator
verbs, add the new tests for default-to-active behaviour and
password-prompt UX, and run every quality gate. Plan completes
when this phase is green.

- [ ] `P09.S84` - rewrite the lifecycle CLI verbs test against the new ten-verb surface; `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`.
- [ ] `P09.S85` - delete the legacy verb tests in the same commit as the rewrite lands; `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`.
- [ ] `P09.S86` - add the default-to-active behaviour test for `show`, `edit`, `export`; `src/aeat/entrypoints/cli/test_profile_default_active.py`.
- [ ] `P09.S87` - add the `switch` password-prompt UX test (correct password, wrong password, three-strikes); `src/aeat/entrypoints/cli/test_profile_switch_password.py`.
- [ ] `P09.S88` - add the `logout` session-state-transition test; `src/aeat/entrypoints/cli/test_profile_logout.py`.
- [ ] `P09.S89` - add the `create --copy-from` end-to-end test; `src/aeat/entrypoints/cli/test_profile_copy_from.py`.
- [ ] `P09.S90` - add the `delete` double-confirm refusal-on-wrong-name test; `src/aeat/entrypoints/cli/test_profile_delete_confirm.py`.
- [ ] `P09.S91` - add the `list --with-status` enrichment columns test; `src/aeat/entrypoints/cli/test_profile_list_with_status.py`.
- [ ] `P09.S92` - add the top-level help discoverability test asserting every profile verb is advertised; `src/aeat/entrypoints/cli/test_config_help_advertises_profile.py`.
- [ ] `P09.S93` - update the apex workflow verification test to reflect the deletion of `init` wiring; `src/aeat/entrypoints/cli/test_apex_workflow_verification.py`.
- [ ] `P09.S94` - run the full pytest suite and resolve every failure; `src/aeat`.
- [ ] `P09.S95` - run `ruff check` and resolve every diagnostic; `src/aeat`.
- [ ] `P09.S96` - run `mypy` and resolve every diagnostic; `src/aeat`.
- [ ] `P09.S97` - run the vault audit and confirm no new errors; `.vault`.
- [ ] `P09.S98` - run the manual operator smoke (fresh root, create, switch, logout, switch back, edit, export, import, delete) and capture the transcript; `.vault/exec/2026-05-16-profile-lifecycle-cli`.
