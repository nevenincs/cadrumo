---
tags:
  - '#reference'
  - '#runtime-authority-boundary'
date: '2026-10-18'
modified: '2026-10-18'
body_schema: 'body-v2'
body_hash: 'sha256:227efd3892410214342e83a148fcaa83ca3517b45f144bb65c816e71c1a92db8'
related:
  - "[[2026-10-10-mcp-parity-sign-in-doors-reference]]"
  - "[[2026-10-04-application-sign-in-reference]]"
---

# `runtime-authority-boundary` reference: `Runtime authority placement census`

This census records where login, session, lease, custody, KDF, throttle, receipt and automation-access code lives on 2026-10-18, who calls it, and where it is duplicated. It was gathered by read-only mapping of `src/`, `dev/` and `.importlinter` with targeted grep and one live graph query of the command tree. Semantic code search (`vaultspec-rag`) was not used; discovery ran on grep and the vault search. Every locator is a current-code observation to re-verify before editing.

## Summary

- The runtime already hosts the login protocol. The client sends `ProfileLogin` (`src/cadrumo_client/contracts/profile_access.py:80`), the runtime answers `SecretReady`, and the secret travels in a separate `S` frame (`src/cadrumo_client/transport/frame_io.py:261-285`). The handler chain is `src/cadrumo_runtime/host/profile_connection_sessions.py:412` (dispatch at `:470`) to `SessionAuthorityAdmission.admit_human` (`src/cadrumo_runtime/application/session_authority_admission.py:276`) to the profile worker's `ProfileWorkerHumanLogin.authenticate` (`src/cadrumo_runtime/host/profile_login.py:97`).
- The runtime does not implement the authentication itself. It imports it from the tax package: about 268 import lines from `cadrumo.application.user_profile`, 7 from `master_key`, and about 39 from `custody`. The worker's password proof calls `authenticate_profile_candidate` (`src/cadrumo/application/user_profile/login_session.py:438`, called at `src/cadrumo_runtime/host/profile_login.py:104`). Throttle, receipts, the sign-in generation, KDF supervision, worker custody and automation stores are all defined under `src/cadrumo`.
- The CLI keeps a second, in-process login. `aeat config login` itself goes to the runtime (`src/cadrumo_client/commands/custody.py:224-278`), but the leaf gate keeps a runtime-free branch that unwraps the DEK in the CLI process (finding A below).
- Profile creation, TUI registration and recovery enrolment run in the frontend process and generate or unwrap the DEK there (finding C).
- The reverse conflation also exists. Frontend code is hosted under `src/cadrumo_runtime/host/frontend/` (67 modules), including the TUI login screen, which contradicts the 2026-10-15 ownership correction in `2026-07-01-import-centralization-adr` (finding E).

## Finding A: the CLI authenticates in-process

- The gate entry is `preflight_parsed_leaf` (`src/cadrumo/entrypoints/cli/_profile_authentication_gate.py:623-709`), imported by `src/cadrumo/entrypoints/cli/command_lifecycle.py:36`. It first tries the runtime route `_activate_profile_connection_leaf` (`:684`, `:851-893`). Otherwise it falls back to `_activate_parsed_profile_session` (`:697`, `:569-611`).
- The runtime route is selected by `_uses_profile_connection` (`:614-620`) against the frozenset `_PROFILE_CONNECTION_KEYS` (`:50-304`, 251 keys). Two leaves pick their route by argument: `config_profile_censo_import` uses the runtime only with `--apply`, and `app_modelo_work_report_verify` uses it only without `--document-only`.
- A live graph query on 2026-10-18 found 286 leaves:
  - 248 profile-bound leaves already route through the runtime.
  - 34 leaves are profile-free or bootstrap-exempt.
  - 4 profile-bound leaves stay in-process: `app_modelo_m360_declare`, `app_modelo_m360_list`, `app_modelo_m360_remove` (`src/cadrumo/entrypoints/cli/modelo_m360_commands.py:127-170`) and `app_modelo_work_report_verify`.
  - The in-process modes are therefore those 4 leaves and the censo import preview.
- The in-process chain:
  - `_profile_session_gate.activate_profile_session` (`src/cadrumo/entrypoints/cli/_profile_session_gate.py:247-309`) calls `_resume_or_authenticate` (`:339-390`), then `admit_profile_session` (`src/cadrumo/application/user_profile/session_admission.py:104-153`).
  - Without a live in-process session it returns `CREDENTIALS_REQUIRED` (`session_admission.py:125-130`). The root secret is then taken from `consume_root_fallback` (`_profile_authentication_gate.py:744-773`), or from the terminal prompt `prompt_root_authentication` (`:776-791`, reached from `_profile_session_gate.py:393-413`).
  - Both reach `_authenticate_for_invocation` (`:794-820`), which calls `authenticate_profile_for_invocation` (`src/cadrumo/application/user_profile/login_session.py:580-633`).
- That function performs the following in the CLI process:
  - It evaluates the throttle (`:598-604`).
  - It runs the KDF child and receives the DEK (`_authenticate_candidate_or_record_failure`, `:646-696`; DEK copied at `:666`).
  - It records a failure on a wrong password (`:662`) and resets the throttle on success (`:614`).
  - It binds the session process-globally (`:618-619`).
  - It falls back to `load_settings().cadrumo_secret_passphrase` (`:636-643`).
- The two gate modules import each other: `_profile_session_gate.py:410` imports from `_profile_authentication_gate`, and `_profile_authentication_gate.py:46`, `:510`, `:583`, `:813` and `:870` import from `_profile_session_gate`.
- Both gate modules are imported by these tests, all under `src/cadrumo/entrypoints/cli/tests/`: `test_google_review_cli.py:32`, `test_operation_expedientes_capture.py:29`, `test_operation_filed_single.py:33`, `test_operation_filed_source.py:34`, `test_profile_authentication_gate.py:31-32`, `test_profile_credential_reference_admission.py:13`, `test_profile_api_key_admission.py:15-16`, `test_profile_prompt_refusal.py:10`, `test_sign_in_refusal_rendering.py:22` and `test_operation_ledger_merge.py:23`. `test_operation_ledger_merge.py:119` also patches `preflight_parsed_leaf`.
- `authenticate_profile_for_invocation` is imported by about 30 tax test modules, about 90 runtime test modules, and `dev/ci/tests/test_domain_buckets_payload_version_contract.py:80`.
- Lane G of `2026-10-18-dependency-provisioning-plan` owns the provision entries of `_PROFILE_CONNECTION_KEYS`. Its P07.S20 is closed; P07.S22 (TUI setup) and P07.S23 (`src/cadrumo_harness/mcp/`) are open.

## Finding B: runtime authority defined in the tax package

**Worker custody.**
- `ProfileWorkerCustody` (`src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:31-318`) is one worker process's key session.
  - It validates leases against `runtime_boot_id` (`_validate_lease`, `:67-74`).
  - It installs the DEK (`install`, `:80`), and holds and retires lease-bound key sessions.
- It is instantiated only by the runtime: `src/cadrumo_runtime/host/worker.py:17`, `:105`, `:154`; `worker_service.py:16`; `profile_login.py:19`, `:81`; `operation_authority.py:16`; `operation_host.py:65`; `worker_extension_records.py:12`.
- Its only tax-side consumer is its own test, `master_key/tests/test_profile_worker_custody_lease_window.py`. That test patches `validate_automation_profile_binding` at `:322`.

**Access administration.**
- `src/cadrumo/application/user_profile/access_administration.py` holds the following:
  - `AccessAdministrationAction.MANAGE_RUNTIME` (`:52`) and `AdministrationRequirement.LOCAL_RUNTIME_OWNER` (`:61`).
  - `FreshPasswordAuthorization`, which carries `runtime_boot_id` and `connection_id` (`:105-129`).
  - The proof-currency check against the boot (`:247-256`).
- `ACCESS_LEASE_MAXIMUM` is defined at `access_contracts.py:30`. It is used by `access_administration.py:125`, `automation_administration_service.py:111`, `automation_enrollment.py:124`, `automation_password.py:69`, and by the runtime at `session_authority_admission.py:173`, `:480`, `:568`, `:641`, `approval_sessions.py:123`, `automation_lifecycle_service.py:360` and `enrollment_connections.py:124`.

**`access_contracts.py` mixes two kinds of content** (660 lines, about 785 importing files).
- Operation-declaration and refusal vocabulary used by tax operation definitions, the client and the harness: `AccessAction` (`:47`), `DisclosureCategory` (`:62`), `DisclosurePermission` (`:70`), `AccessScope` (`:99`), `OperationAccessPolicy` (`:538`), `AccessDenialCode` (`:562`) and `AccessDenied` (`:605`).
- Runtime authority records: `AutomationGrant` (`:268`), `ApiKeyRecord` (`:294`), `AccessSession` (`:380`, boot binding at `:393`), `LoginEligibility` (`:442`), `OsLoginContext` (`:464`) and `AccessEvaluationContext` (`:487`, boot at `:500`).

**Automation approval.**
- `AutomationAdministrationService` is in `automation_administration_service.py:76-155`. It checks the requester's boot, connection and client at `:42-47`.
- `ApprovalSession` is in `automation_approval_session.py:136-332`.
- The runtime wraps them in `src/cadrumo_runtime/application/approval_sessions.py:22-23`, `:42`, and uses them from `src/cadrumo_runtime/host/profile_host.py:61` and `enrollment_connections.py:17`.
- The other automation modules (`automation_custody_port`, `automation_enrollment`, `automation_execution`, `automation_lifecycle`, `automation_operations`, `automation_password`) are imported 1 to 37 times each by the runtime.

**Login building blocks.**
- `login_session.py` (773 lines) defines `authenticate_profile_candidate` (`:438-494`), `borrow_profile_receipt_key` (`:556-577`), `publish_created_profile_session` (`:307-376`), `resolve_login_target` (`:403-434`) and the throttle-raising error `ProfileLoginThrottledError` (`:83-98`).
- The port is in `login_session_port.py`: throttle evaluation `:155-224`, receipt mint `:229`.
- The adapter is `src/cadrumo/adapters/persistence/storage/profile_login_session.py:84-102`.

**Throttle.**
- The sidecar is `src/cadrumo/adapters/persistence/storage/master_key/login_throttle.py`: path `:114-118`, cap `:60`, read-as-clear `:121-150`, record `:199-234`, reset `:237-252`.
- Its location is declared in `src/cadrumo/core/storage_taxonomy.py:316` and `src/cadrumo/core/storage_taxonomy_locations.py:838-839`.
- The recovery door evaluates and records it too (`src/cadrumo/application/user_profile/recovery_custody.py:303-332`).
- The runtime only maps the refusal: `profile_login.py:113-118`, `bootstrap_reset.py:153-157`, and `src/cadrumo_runtime/commands/profile_admission.py:253-254`.

**Receipts and sign-in generation.**
- `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py` holds `mint_profile_session` (`:919`), `refresh_profile_session_with_key` (`:1126`), `borrow_profile_session_key` (`:1254`), `resume_profile_session_with_key` (`:1301`) and the keychain write `_store_acceleration_secret` (`:343`).
- `acceleration_receipt_crypto.py:262` unwraps the DEK.
- `sign_in_generation.py:121` is `SignInGenerationCustody`.
- All of them are consumed by the runtime host: `profile_host.py:19-31`, `sign_in_status.py:9-13`, `sign_in_sweep.py:11-20` and `profile_login.py:14-17`.
- `dev/quality/tests/test_receipt_mutation_ownership.py:31-60` pins the receipt writers to the tax-package files `profile_login_session.py`, `login_session_port.py`, `login_session.py` and `custody_service.py`, plus the runtime host files.

**KDF supervision.**
- `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py:24` (`launch_worker`) spawns `python -S -m cadrumo.adapters.persistence.storage.custody._kdf_worker` (`:96`).
- It is driven by `_kdf_worker_supervision.py:374-391`, which `kdf_supervision.py:570`, `:618-623` and `:655` call.
- DEK-returning functions:
  - `unlock_profile_custody` (`kdf_supervision.py:345`)
  - `unlock_profile_custody_password_material` (`:378`, unwrap at `:405`)
  - `unlock_profile_custody_recovery_material` (`:458`)
  - `recovery.py:257`
  - `automation_store.py:49-104`
- `dev/packaging/native/platforms/windows_verify.py:83-127` patches `_kdf_process`.

**Other master-key modules.** `bucket_session.py` (`BucketSession`, DEK buffer at `:91`, `dek` at `:214`), `live_sessions.py`, `idle_timeout.py`, `login_handover_journal.py`, `profile_worker_binding.py`, `master_key_derivation.py:20` and `kdf_params.py`.

**Custody application services.** `custody_service.py`, `custody_transactions.py`, `custody_ports.py` (password unlock at `:1421-1434`), `custody_repository.py`, `passphrase_rotation.py:172`, `recovery_custody.py:193-363`, `capsule_restore.py:191`, `registration.py:226` (DEK generation) and `session_retirement.py`.

## Finding C: frontends handle the DEK during custody acts

- **CLI profile creation.** `aeat config profile create` runs `src/cadrumo/entrypoints/cli/config/profile_commands.py:65`, `:133` and `scripted_registration.py:209-251`, which call `register_profile_with_credentials`.
  - That function generates the DEK (`src/cadrumo/application/user_profile/registration.py:226`) and wraps it through the KDF child (`envelope.py:17-27`, `kdf_supervision.py:424`) in the CLI process.
  - It then calls `publish_created_profile_session` (`registration.py:58`, `:301`).
  - Recovery enrolment after creation (`scripted_registration.py:154`) unwraps in-process.
- **TUI registration and recovery.** `src/cadrumo/entrypoints/tui/secret/registration.py:926-936` does the same, and logs `runtime_admitted: False` at `:979`. `:999` enrols recovery in the TUI process (`recovery_custody.py:193`, `:355-363`).
- **TUI passphrase rotation.** `src/cadrumo/entrypoints/tui/secret/passphrase.py` takes an injected `rotate` callable. Its default is wired at `src/cadrumo/application/auth/operation_definitions.py:201` and `:506`. The process that runs it was not confirmed.
- **Runtime installation acts already exist** for `profile_list`, `archive_inspect`, `archive_import_prepare`, `archive_import`, `recovery_enroll` and `reset_*` (`src/cadrumo_client/contracts/installation_requests.py:254-404`; served by `src/cadrumo_runtime/host/installation_profiles.py:93-204`). There is no profile-creation act.

## Finding D: wire shapes defined in the tax package

The frontends import refusal and status shapes from `cadrumo.application.user_profile`.

- `SignInRefusal` is defined in `sign_in_refusals.py:11-25`. It is used by `src/cadrumo_runtime/host/profile_login.py:113-121` and `src/cadrumo_client/contracts/profile_access.py:258` (`AccessRefusal.sign_in`).
- `ProfileReceiptRefusedError` (`login_session.py:216`) is raised and caught in `src/cadrumo_client/transport/frontend_client.py:94-121`, `src/cadrumo_client/commands/profile_admission.py:134` and `src/cadrumo_client/commands/custody.py`.
- `ProfileLoginThrottledError` is rebuilt from a `throttled` reply at `frontend_client.py:911-914`.
- `ProfileLoginOutcome` (`login_session.py:109-147`) is used by `src/cadrumo_runtime/contracts/profile_worker.py:27`, `:368` and `src/cadrumo_client/commands/custody.py`.
- `AutomationCustodyCode` is defined in `automation_custody_port.py:82-87`. A wrong password is the generic `CREDENTIAL_REJECTED` (`profile_login.py:121`, `profile_connection_admission.py:264`), not a sign-in reason.
- The client reads the keychain proof through the tax package: `frontend_client.py:417-425` calls `borrow_profile_receipt_key`, and `src/cadrumo_client/commands/custody.py:145-406` calls `resolve_login_target` and `profile_session_keychain_unavailability`.
- The harness imports `access_contracts`, `sign_in_refusals`, `automation_custody_port`, `automation_enrollment` and `profile_operation_contracts` from the tax package. It imports nothing from `login_session` or `cadrumo.entrypoints`.
- Across `src/cadrumo_client`, 98 non-test modules import `cadrumo.*` (all subjects, not only authentication).

## Finding E: frontend code hosted by the runtime

- `src/cadrumo_runtime/host/frontend/cli/` (`app.py`, `bootstrap.py`, `profile_client.py`, `profile_services.py`, `tui_launcher.py`, `windows_secret_bootstrap.py`) and `src/cadrumo_runtime/host/frontend/tui/` hold 67 modules.
- These include the TUI login screen (`tui/secret/runtime_login.py:41`, submit `:209-233`), the login attempt (`runtime_login_attempt.py:133-158`), recovery (`runtime_login_recovery.py:37-56`), installed-session opening (`installed_session.py:157-197`, which closes a bucket session at `:24`) and the automation inventory screens.
- They reach the runtime through `cadrumo_client` calls and import about 60 `cadrumo.entrypoints.tui` symbols.
- `import_load_targets.cadrumo_runtime.json:189` lists `cadrumo_runtime.host.frontend.tui.secret.runtime_login_session`.

## Finding F: frontends read and write the active-profile pointer

The active-profile pointer is the durable "who is selected" record (`src/cadrumo/core/bucket_pointer.py`, with transactions in `src/cadrumo/application/user_profile/profile_pointer.py`). The parallel boundary-fix workstream stopped on it, because frontends resolve the selected profile by reading this file directly.

- **Readers.** These frontends read it:
  - the MCP harness: `selected_profile_id`, `src/cadrumo_harness/mcp/runtime_admission.py:67-87`;
  - the CLI gates: `_profile_session_gate.py:96-97` and `:266`, and `_profile_authentication_gate.py:879`;
  - the client commands: `src/cadrumo_client/commands/custody.py:239` (`observe_active_profile_pointer`) and `src/cadrumo_client/commands/profile_admission.py`;
  - the runtime's own CLI: `src/cadrumo_runtime/commands/activity.py`, `passphrase.py`, `presentation.py`, `profile_admission.py`, `profile_support.py` and `sign_in_status.py`.
- **A writer.** `src/cadrumo_client/commands/custody.py:287` opens `active_profile_pointer_transaction` in the frontend process after a runtime login, so the selection is written by the client, not by the runtime.
- **Why no runtime query covers it.** `client.status()` cannot answer, because it needs a client already opened for a profile. `SignInStatusRequest` (`src/cadrumo_client/contracts/sign_in.py:44-55`) takes a `profile_id` and reports presence and deadlines for that one profile only. No request answers "which profile holds the live sign-in or the selection" without a profile.
- **Tax readers.** About 45 more tax-package modules call `resolve_active_bucket_id` or the pointer transactions. They span `src/cadrumo/application/` (auth, modelo export and selection, workflow, wizard, storage management, state projection, user_profile) and `src/cadrumo/adapters/` (AEAT browser factory, Cl@ve, Google, attachment, runtime repository), plus about 15 CLI support modules. Inside the profile worker these want the worker's bound profile (`profile_worker_binding.py`), not the selection. In a frontend process they read the file directly. Each needs per-call classification before it changes.
- **The desktop profile list.** The desktop's runtime-free profile list (`aeat --format json config profile list`) reports each profile's selected flag from the same file.

## Duplication

These pairs implement the same responsibility twice and are candidates for deletion rather than relocation:

- **Human admission.** `session_admission.admit_profile_session` with `authenticate_profile_for_invocation` (tax, in-process) against `SessionAuthorityAdmission.admit_human` with `ProfileWorkerHumanLogin.authenticate` (runtime). Both run the throttle and the KDF.
- **Lease validation.** `ProfileWorkerCustody._validate_lease` (`profile_worker_custody.py:67-74`) and `access_contracts._validate_origin_and_lease` (`:410`) against `src/cadrumo_runtime/adapters/worker_authorization_lease.py:294` and `src/cadrumo_runtime/application/session_authority_core.py:84-88`. These overlap in purpose; whether the checks are identical is unverified.
- **Profile admission doors.** `src/cadrumo_client/commands/profile_admission.py:113-198` (used by `src/cadrumo_runtime/host/frontend/cli/app.py:27`) and `src/cadrumo_runtime/commands/profile_admission.py:41-298` both resume, then prompt, then present a password. Their divergence is unverified.
- **Login target resolution.** `resolve_login_target` is called by the client, the runtime commands, the runtime host and the CLI wrapper `_resolve_login_target_or_refuse` (`_profile_authentication_gate.py:399-455`).

## Process boundaries the DEK crosses today

- KDF child to parent: the DEK result frame (`_kdf_worker.py:72`, read at `_kdf_worker_supervision.py:211`). Parent to child, for a wrap: `dek_b64` in the request (`:227`).
- Runtime host to profile worker: a secret frame after the install document (`src/cadrumo_runtime/adapters/profile_worker_transport.py:132-140`, `:257`; read at `src/cadrumo_runtime/host/worker_service.py:199-201`). This is used after an automation unwrap in the host (`session_owner.py:292`, `session_authority_admission.py:234`).
- Human login unwraps inside the worker and installs in-process (`profile_login.py:198-200`). No DEK frame is used for it.
- In-process fallback: the CLI or TUI process receives the DEK (findings A and C). This is the only crossing into a frontend.
- Tax persistence reads the bound key through `get_active_master_key` and `get_active_hmac_subkey` (`src/cadrumo/adapters/persistence/storage/master_key/active_session.py:144`, `:163`). Its consumers include `crypto/encrypted_columns.py`, `sql/secure_objects.py`, `blob_store/blob_store.py`, `secret_store/store.py`, `llm/consent_ledger.py`, `operator_scope.py` and `outbound/aeat/auth/clave_movil.py`.

## Enforcement today

- **Import contracts.** `.importlinter` forbids `cadrumo` from importing `cadrumo_runtime` (`:220-227`) and `cadrumo_client` from importing it (`:229-236`). It forbids `cadrumo` from importing `cadrumo_client.transport.installed_client`, `credentials` and `commands.profile_admission` (`:238-247`). It contains no `ignore_imports`.
  - No contract names `user_profile`, `master_key`, `custody`, `keyring` or `argon2`.
  - Nothing stops the CLI from reaching `master_key` or the KDF.
- **Third-party imports.** `keyring` and `argon2` are imported in the tax package by the custody modules (`acceleration_receipt.py`, `kdf_supervision.py`, `_kdf_records.py`, `_kdf_worker.py`, `kdf_params.py`, `master_key_derivation.py`). `argon2` is also imported by `src/cadrumo/application/user_profile/bundle_encryption.py`, the portable-bundle passphrase, which is a tax export rather than a login.
- **Module metadata.** `dev/quality/metadata/import_load_targets.cadrumo.json:414`, `:1568-1661`, `:2613-2614` and `dev/quality/metadata/application_entrypoint_modules.json:1137-1483` list the affected modules.
