---
tags:
  - '#plan'
  - '#runtime-authority-boundary'
date: '2026-10-18'
tier: L2
related:
  - '[[2026-10-18-runtime-authority-boundary-adr]]'
modified: '2026-10-18'
body_schema: body-v2
body_hash: 'sha256:d712cbb290bee6ba28bc19ef6098267fa1abaf9b4a8910b65a1ccdd8f4d2ca50'
---

# `runtime-authority-boundary` plan

Move login, session, lease and custody authority into `src/cadrumo_runtime`, put its wire shapes in `src/cadrumo_client/contracts`, and leave `src/cadrumo` with presentation, tax facts and an inward key port.

## Description

Approved 2026-10-18. Basis: the user's ruling of 2026-10-18, relayed verbatim by the orchestrating session: "be careful not to conflate runtime a higher level construct with the cli tui mcp. those require a runtime but do not manage them. ensure there's no runtime management code in the cadrumo/ src". The ruling directs this outcome. It does not settle the open decisions below, and Steps gated on them do not execute until the user answers.

**Decision coverage.**
- `2026-10-18-runtime-authority-boundary-adr` (accepted) governs every Phase. It sets:
  - the target ownership;
  - the client contract;
  - what moves, what is deleted and what stays;
  - the DEK and custody invariants;
  - parity;
  - the order of the move.
- Its census is `2026-10-18-runtime-authority-boundary-reference`.
- It amends `2026-08-13-profile-session-lifecycle-successor-adr`, `2026-08-13-profile-password-custody-rollup-adr`, `2026-08-13-profile-state-aggregate-successor-adr`, `2026-10-04-application-sign-in-adr`, `2026-09-26-mcp-purpose-authentication-adr`, `2026-09-26-mcp-purpose-authentication-profile-access-adr` and `2026-10-12-mcp-parity-attended-live-sign-in-adr`. Their persisted formats, lifetimes, throttle rules and MCP admission doors stay binding on every Step.
- `2026-07-01-import-centralization-adr` governs how each move is made: definition, owning tests, every consumer, dynamic targets and metadata in one commit, with no alias, shim or re-export.

**Open decisions and their gates.**
- **OD1 (no runtime-free profile act)** gates P03.S08, P03.S09, P04.S10, the selected-flag part of P03.S21, and everything in P05 and P06 that depends on deleting a runtime-free path. All other Steps are additive and may proceed.
- **The active-profile query and runtime-owned pointer** (P02.S20, P03.S21, P05.S22, and the harness part of P01.S03) come from a design addition the coordinator relayed on 2026-10-18. The boundary-fix workstream stopped on the frontends' direct pointer reads. The addition sits inside the ADR's accepted scope.
- **OD2 (the rest of `src/cadrumo_runtime/host/frontend/`)** is outside this plan. If the user folds it in, it is added as a new Phase through the plan verbs.

**Scope boundaries.**
- Provider authentication (AEAT certificate and Cl@ve, Google) is out of scope.
- The non-authentication imports from `cadrumo_client` into the tax package are out of scope.
- Persisted bytes never change. A Step that would need a format migration stops and returns to the orchestrator.

## Steps

### Phase `P01` - client wire contracts

Publish the authentication wire shapes and the operation-declaration access vocabulary in the client contracts, so that frontends, the harness and the runtime stop importing them from the tax package.

- [x] `P01.S01` - Move the sign-in refusal set, the admitted login status and the receipt and throttle refusal errors into a client-contract module, add the `credential_rejected` reason in place of the generic credential code for a wrong password, and rewire the runtime, client and tax frontend consumers with their tests and import-load metadata, leaving the harness to P01.S03; `src/cadrumo_client/contracts/ (new sign-in module), src/cadrumo/application/user_profile/sign_in_refusals.py (deleted), the shapes in login_session.py, consumers under src/cadrumo_runtime/, src/cadrumo_client/ and src/cadrumo/entrypoints/, dev/runtime_lifecycle/, dev/quality/metadata/`.
- [x] `P01.S02` - Move the operation-declaration access vocabulary and the wire codes of `access_contracts.py` and `automation_custody_port.py` into client-contract modules in atomic slices per symbol family, leaving grants, key records, sessions, eligibility, evaluation context and the lease maximum for P05.S13; `src/cadrumo_client/contracts/ (new access vocabulary modules), src/cadrumo/application/user_profile/access_contracts.py, automation_custody_port.py, every consumer under src/ and dev/, dev/quality/metadata/`.
- [x] `P01.S03` - Rewire the MCP harness to the client-contract shapes, replace its pointer read in selected_profile_id with the runtime's active-profile query while keeping its profile-mismatch refusal, and confirm it imports nothing authentication-related or pointer-related from the tax package; `src/cadrumo_harness/mcp/runtime_admission.py, src/cadrumo_harness/ and its tests`.

### Phase `P02` - runtime doors

Give the runtime every door a frontend needs to present a secret: profile creation, rotation, reset and recovery as installation acts, login by profile name, and one client-side admission door with proof presentation in the client transport.

- [x] `P02.S04` - Add the profile-creation installation act, which takes the password and its confirmation on the secret frame and in the runtime generates the DEK, writes the envelope, publishes the capsule, writes the initial profile record through the composed tax repository and returns the profile selected and signed out; `src/cadrumo_client/contracts/installation_requests.py, src/cadrumo_client/transport/installation_client.py, src/cadrumo_runtime/host/installation_profiles.py, installation_door.py, and tests`.
- [x] `P02.S05` - Serve password rotation, password reset and recovery enrolment and removal as runtime acts reachable from every person frontend, adding any act a frontend performs in-process today; `src/cadrumo_client/contracts/installation_requests.py, profile_access.py, src/cadrumo_client/transport/, src/cadrumo_runtime/host/installation_profiles.py, profile_connection_admission.py, src/cadrumo_runtime/commands/passphrase.py, recovery.py, and tests`.
- [x] `P02.S06` - Resolve login targets in the runtime from the operator's profile name or UUID, move receipt-proof presentation and keychain naming into the client transport and contracts so that `cadrumo_client` imports nothing from `login_session`, and merge the two profile-admission doors into the client-side door used by both executables; `src/cadrumo_client/transport/frontend_client.py, src/cadrumo_client/commands/profile_admission.py, custody.py, src/cadrumo_runtime/commands/profile_admission.py and its importers, src/cadrumo_runtime/host/profile_receipt.py, profile_connection_admission.py, and tests`.
- [x] `P02.S20` - Add the no-session active-profile query, which reports the signed-in profile, the selected profile and their presence with the sign_in_changed watch cue and grants nothing, make the runtime the only pointer writer at login, creation, logout and deletion, and remove the pointer transaction from the client's config login and logout; `src/cadrumo_client/contracts/sign_in.py or a new client-contract module, src/cadrumo_client/transport/frontend_client.py, src/cadrumo_client/commands/custody.py, profile_admission.py, src/cadrumo_runtime/host/profile_connection_sessions.py, sign_in_status.py, installation_profiles.py, bootstrap_delete.py, src/cadrumo_runtime/commands/ pointer readers, and tests`.
- [x] `P02.S23` - Close the runtime commands' indirect reach into product setup and Google code, approved by the principal on 2026-10-18 under the client-contract rule of the governing ADR: move the Google error and refusal vocabulary the client commands use, the wire failure categories, and the runtime server-start operation ids into client contracts; move commands tests that need the composed host to the host seam; and set allow_indirect_imports to False on runtime-commands-know-no-product-setup; `src/cadrumo_client/contracts/ (new Google, failure-category and operation-id modules), src/cadrumo/adapters/outbound/google/errors.py, src/cadrumo/application/dependency_contracts.py, src/cadrumo/application/user_profile/google_configuration_operation_*.py, src/cadrumo_client/commands/google_*.py, src/cadrumo_runtime/adapters/worker_authorization.py, src/cadrumo_runtime/commands/tests/ (moved), src/cadrumo_runtime/host/tests/, .importlinter, dev/quality/metadata/`.

### Phase `P03` - CLI door cutover

Route every profile-bound CLI leaf and profile creation through the runtime, then delete the in-process CLI authentication and its route selection.

- [ ] `P03.S07` - Route the M360 declare, list and remove leaves, the document-only report verification and the censo import preview through runtime-hosted registered operations and the profile connection, with their refusal and output-shape tests; `src/cadrumo/entrypoints/cli/modelo_m360_commands.py, the M360, report-verification and censo preview operation definitions, src/cadrumo/entrypoints/cli/command_operation_table.py (these rows only), the registration lines of src/cadrumo/entrypoints/operation_composition.py, and tests`.
- [ ] `P03.S21` - Replace every frontend pointer read in the CLI gates and CLI support modules with the active-profile query, classify each tax-package pointer reader as worker-side, which moves to the worker's bound profile, or frontend-side, which moves to the query, and source the profile list's selected flag from the query, reporting it unavailable with no runtime once OD1 is confirmed; `src/cadrumo/entrypoints/cli/_profile_session_gate.py, _profile_authentication_gate.py, _root_support.py, common.py, the config and modelo CLI support modules that call resolve_active_bucket_id, the tax application and adapter readers listed in the reference finding F, and tests`.
- [ ] `P03.S08` - Send `aeat config profile create` and its optional recovery enrolment through the runtime acts, presenting the password on the secret frame and keeping the typed refusals undiminished; `src/cadrumo/entrypoints/cli/config/scripted_registration.py, profile_commands.py, src/cadrumo/entrypoints/cli/config/tests/`.
- [ ] `P03.S09` - Delete the in-process CLI authentication (`session_admission.py`, `authenticate_profile_for_invocation`, the settings passphrase fallback, the credential path of `_resume_or_authenticate`, `consume_root_fallback`, `prompt_root_authentication`, `_authenticate_for_invocation`) and the `_PROFILE_CONNECTION_KEYS` route selection, so that every profile-bound leaf presents through the runtime, and move or delete their tests; `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py, _profile_session_gate.py, src/cadrumo/application/user_profile/session_admission.py (deleted), login_session.py, src/cadrumo/core/config.py (the passphrase setting only), src/cadrumo/entrypoints/cli/tests/, dev/ci/tests/test_domain_buckets_payload_version_contract.py`.

### Phase `P04` - TUI door cutover

Send TUI registration, recovery and password rotation through the runtime acts, and move the runtime-hosted login and secret screens into the TUI package.

- [ ] `P04.S10` - Send TUI registration, recovery enrolment and password rotation through the runtime acts, so that no TUI path generates, wraps or unwraps a DEK; `src/cadrumo/entrypoints/tui/secret/registration.py, passphrase.py, the rotation wiring in src/cadrumo/application/auth/operation_definitions.py, and tests`.
- [ ] `P04.S11` - Move the runtime-hosted TUI login and secret screens into `cadrumo.entrypoints.tui.secret`, presenting only through the client, and update their launch references and import-load metadata; `src/cadrumo_runtime/host/frontend/tui/secret/ (moved), src/cadrumo/entrypoints/tui/secret/, src/cadrumo_runtime/host/frontend/tui/installed_session.py, launcher.py, dev/quality/metadata/, and tests`.

### Phase `P05` - runtime application services

Move the login, session, access-administration, automation and custody application services from the tax package into the runtime application layer.

- [ ] `P05.S12` - Move login, receipt and throttle orchestration and session retirement into the runtime application layer, delete `publish_created_profile_session`, and move their tests; `src/cadrumo/application/user_profile/login_session.py, login_session_port.py, login_interaction.py, session_retirement.py, authentication.py, src/cadrumo_runtime/application/, runtime consumers, and tests`.
- [ ] `P05.S13` - Move access administration, access policy and projections, the runtime records of `access_contracts.py` and the automation modules into the runtime application layer, merging them with the runtime's approval and lifecycle services where they duplicate; `src/cadrumo/application/user_profile/access_*.py, automation_*.py, src/cadrumo_runtime/application/, runtime consumers, and tests`.
- [ ] `P05.S14` - Move the custody application services into the runtime application layer: custody service, transactions, ports and repository, password rotation, prospective password, recovery custody and its operations, the custody part of registration, capsule restore and capsule archive; `src/cadrumo/application/user_profile/custody_*.py, passphrase_rotation.py, prospective_password.py, recovery_*.py, registration.py, capsule_restore.py, capsule_archive.py, src/cadrumo_runtime/application/, and tests`.
- [ ] `P05.S22` - Move the pointer transactions and the pointer primitive into the runtime once no tax-package reader remains, or record in this Step's ledger note the reader that keeps the read primitive in the tax package and why; `src/cadrumo/application/user_profile/profile_pointer.py, profile_pointer_ports.py, src/cadrumo/core/bucket_pointer.py, src/cadrumo_runtime/application/, and tests`.

### Phase `P06` - runtime custody adapters

Move worker custody, the key-holding session, KDF supervision, envelope, recovery, receipts, throttle, sign-in generation and automation stores into the runtime adapters, leaving the tax package an inward key port.

- [ ] `P06.S15` - Define the inward key port in the tax package and bind it from the runtime worker, move the key-holding session, live sessions, idle timeout, worker binding and worker custody into the runtime adapters, and let tax persistence and its test support read key material only through the port; `src/cadrumo/adapters/persistence/storage/master_key/active_session.py (becomes the port), bucket_session.py, live_sessions.py, idle_timeout.py, profile_worker_binding.py, profile_worker_custody.py, the key consumers under src/cadrumo/adapters/, src/cadrumo_runtime/adapters/, src/cadrumo_runtime/host/worker*.py, and tests`.
- [ ] `P06.S16` - Move KDF supervision and its worker modules, the envelope, recovery, sentinel, KDF parameters and key derivation into the runtime adapters, together with the packaging verifier's patch target and the per-file lint ignore; `src/cadrumo/adapters/persistence/storage/custody/_kdf_*.py, kdf_supervision.py, kdf_calibration_search.py, envelope.py, recovery.py, sentinel*.py, master_key/kdf_params.py, master_key_derivation.py, src/cadrumo_runtime/adapters/, dev/packaging/native/platforms/windows_verify.py, pyproject.toml (that ignore only), and tests`.
- [ ] `P06.S17` - Move receipts, the sign-in generation, the throttle, the handover journal, the automation stores, the native keychain modules, `profile_login_session.py` and `profile_custody.py` into the runtime adapters, with the neutral native credential-store primitive in the client transport; `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt*.py, sign_in_generation.py, automation_*.py, macos_*.py, linux_secret_*.py, gnome_collection_protection.py, master_key/login_throttle.py, login_handover_journal.py, src/cadrumo/adapters/persistence/storage/profile_login_session.py, profile_custody.py, src/cadrumo_runtime/adapters/, src/cadrumo_client/transport/, and tests`.

### Phase `P07` - enforcement

Make the boundary a build failure through Import Linter, and retarget the ownership gate, metadata and generated API pages to the moved code.

- [ ] `P07.S18` - Add the Import Linter contract that forbids the tax package from importing `keyring` and the native credential-store bindings, and prove it with a planted-defect test; `.importlinter, dev/quality/tests/ (planted-defect test)`.
- [ ] `P07.S19` - Retarget the receipt-ownership gate, the import-load and entrypoint metadata and the generated API pages to the moved modules, confirm no stale entry names a deleted module, and propose corrected custody locators for rules 02 and 05 to the user; `dev/quality/tests/test_receipt_mutation_ownership.py, dev/quality/metadata/, docs/api/ (through its generator)`.

## Parallelization

Seven lanes, one per Phase, named RA-1 to RA-7 so that they cannot be confused with the lanes of `2026-10-18-dependency-provisioning-plan`.

**How lanes work.**
- Each lane runs one implementer with its own read-only haiku fleet.
- All lanes work in the shared `tui` worktree. Nobody creates a worktree or a snapshot checkout.
- A lane writes only inside its write set. A change outside it goes to the owning lane through the orchestrator.
- Each Step is one commit of its own paths, made with plain `git add <paths>` and `git commit`. Its rows are logged with `vaultspec-core vault exec log --feature runtime-authority-boundary --step <S##> --related 2026-10-18-runtime-authority-boundary-plan`.
- Shared files are re-read before every patch. Formatters and linters run on literal path lists only.

**External holds.**
- **Dependency-provisioning Lane G** owns the provision entries of `_PROFILE_CONNECTION_KEYS`, the TUI navigation registration (P07.S22) and `src/cadrumo_harness/mcp/` (P07.S23).
- **Dependency-provisioning Lane A** owns the registration lines of `src/cadrumo/entrypoints/operation_composition.py` and `src/cadrumo/application/operations/access_facts.py`.
- **Dependency-provisioning Lane E** owns `src/cadrumo_runtime/host/session_hold.py`. **Lane D** owns `src/cadrumo_runtime/commands/google.py` and `google_auth_specs.py`. No lane here writes those files.
- **The parallel boundary-fix workstream** owns `reset_cli`, `operation_installation`, `storage_materialization`, the harness `runtime_admission` and `.importlinter`. No lane here writes them until the orchestrator reports that workstream landed.

**Hard ordering.**
- P01.S01 lands first, because every lane imports its shapes.
- P05 starts only after P03, P04 and P01.S02 are closed, because a tax-package consumer of a moved module would break the import contract.
- P06 starts only after P05 closes. P07 runs last.

**The lanes:**
- **Lane RA-1, P01 (contracts).**
  - Writes: new modules under `src/cadrumo_client/contracts/`; `src/cadrumo/application/user_profile/sign_in_refusals.py`; the shapes in `login_session.py`, `access_contracts.py` and `automation_custody_port.py`; and the consumer import lines and metadata those moves require.
  - Depends:
    - S01 depends on nothing.
    - S02 rewrites imports across the whole tree, so it waits until `2026-10-18-dependency-provisioning-plan` has closed every lane except H, then runs with no other lane mid-Step.
    - S03 waits for P02.S20, dependency-provisioning P07.S23, and the orchestrator's confirmation that the boundary-fix workstream has released `src/cadrumo_harness/mcp/runtime_admission.py` to this lane.
  - Verify: `uv run --no-sync pytest src/cadrumo_client src/cadrumo_runtime/host/tests src/cadrumo/entrypoints/cli/tests -k "sign_in or refusal or login or access" -q`, `uv run --no-sync lint-imports --config .importlinter --no-cache`, and `just check-types` on the touched modules.
- **Lane RA-2, P02 (runtime doors).**
  - Writes: `src/cadrumo_client/contracts/installation_requests.py` and `profile_access.py`; `src/cadrumo_client/transport/installation_client.py`, `frontend_client.py` and `profile_transport.py`; `src/cadrumo_client/commands/profile_admission.py` and `custody.py`; `src/cadrumo_runtime/host/installation_profiles.py`, `installation_door.py`, `profile_connection_admission.py`, `profile_connection_sessions.py`, `profile_receipt.py`, `sign_in_status.py` and `bootstrap_delete.py`; `src/cadrumo_client/contracts/sign_in.py`, or the new module for the active-profile query; `src/cadrumo_runtime/commands/profile_admission.py`, `passphrase.py`, `recovery.py`, `activity.py`, `presentation.py`, `profile_support.py` and `sign_in_status.py`; and their tests.
  - Depends on P01.S01. May run beside RA-3's S07. S20 runs after S06, because both rewrite `frontend_client.py` and the admission door.
  - Verify: `uv run --no-sync pytest src/cadrumo_runtime/host/tests src/cadrumo_runtime/commands/tests src/cadrumo_client -k "installation or profile_create or recovery or passphrase or receipt or admission" -q` through the real runtime with synthetic profiles. Also confirm by test that creation leaves the profile signed out and that a wrong password returns `credential_rejected` and records the throttle.
- **Lane RA-3, P03 (CLI).**
  - Writes: `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py`, `_profile_session_gate.py`, `modelo_m360_commands.py` and `command_operation_table.py` (the S07 rows only); `src/cadrumo/entrypoints/cli/config/scripted_registration.py` and `profile_commands.py`; the M360, report-verification and censo-preview operation definitions; `src/cadrumo/application/user_profile/session_admission.py`; the in-process functions of `login_session.py`; the passphrase setting in `src/cadrumo/core/config.py`; and the CLI tests.
  - Depends:
    - S07 depends on P01.S01. Its registration lines go through dependency-provisioning Lane A's owner.
    - S21 depends on P02.S20. Its tax-application and adapter readers lie outside this lane's other files, so it also writes the readers listed in the reference finding F. It re-reads each of them before patching, and coordinates with the owner of any reader that an in-flight plan holds. Its selected-flag change waits for OD1.
    - S08 depends on P02.S04, P02.S05 and OD1.
    - S09 depends on S07, S08, OD1, and the close of dependency-provisioning P07, since it deletes `_PROFILE_CONNECTION_KEYS`.
  - Verify: `uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests -q`, `just check-operation-contract-manifest`, and the live CLI registration, refusal and output-shape checks of rule 01.
- **Lane RA-4, P04 (TUI).**
  - Writes: `src/cadrumo/entrypoints/tui/secret/`; `src/cadrumo_runtime/host/frontend/tui/secret/` (moved out); `src/cadrumo_runtime/host/frontend/tui/installed_session.py` and `launcher.py` (launch references only); the rotation wiring in `src/cadrumo/application/auth/operation_definitions.py`; and their tests.
  - Depends:
    - S10 depends on P02.S04, P02.S05 and OD1.
    - S11 depends on P02.S06, and re-reads the TUI navigation registration against dependency-provisioning P07.S22.
  - Verify: `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests src/cadrumo_runtime/host/tests -k "login or registration or passphrase or recovery or secret" -q`, and a simulated TUI login against a real runtime that resumes a receipt, then signs in by password, then shows `throttled` with its remaining seconds.
- **Lane RA-5, P05 (application services).**
  - Writes: the `src/cadrumo/application/user_profile/` modules named in S12 to S14 (moved out); `src/cadrumo_runtime/application/`; and the runtime and test consumers of those modules.
  - Depends on P01.S02, P03, P04 and OD1. Its Steps run serially, because they share consumers. S22 runs last, after S21 has removed the tax readers it can.
  - Verify: `uv run --no-sync pytest src/cadrumo_runtime -q` and `uv run --no-sync pytest src/cadrumo/application/user_profile/tests -q`, plus `uv run --no-sync lint-imports --config .importlinter --no-cache`.
- **Lane RA-6, P06 (adapters).**
  - Writes: the `src/cadrumo/adapters/persistence/storage/master_key/` and `custody/` modules named in S15 to S17 (moved out); `profile_login_session.py` and `profile_custody.py`; the key consumers under `src/cadrumo/adapters/`; `src/cadrumo_runtime/adapters/`; `src/cadrumo_runtime/host/worker*.py`; the credential-store primitive in `src/cadrumo_client/transport/`; `dev/packaging/native/platforms/windows_verify.py`; the one lint ignore in `pyproject.toml`; and their tests.
  - Depends on P05. Its Steps run serially.
  - Verify:
    - `uv run --no-sync pytest src/cadrumo/adapters/persistence src/cadrumo_runtime -q`.
    - The format fixtures of the plan Verification.
    - The packaged KDF attestation lane, run small and serial and agreed with the live build session first.
- **Lane RA-7, P07 (enforcement).**
  - Writes: `.importlinter` (after the boundary-fix workstream); `dev/quality/tests/`; `dev/quality/metadata/`; and the generated `docs/api/` pages through their generator.
  - Depends on P06.
  - Verify: `uv run --no-sync lint-imports --config .importlinter --no-cache` passes, and fails on the planted defect; `uv run --no-sync pytest dev/quality/tests -q`.

## Verification

The plan is complete when every Step is closed and the final review passes. A formal review runs at each Phase close and at plan close.

**Boundary.**
- `uv run --no-sync lint-imports --config .importlinter --no-cache` passes with the new contract.
- The planted-defect test proves that a tax-package import of `keyring` or of a native credential-store binding fails it.
- A filesystem listing finds no `src/cadrumo/adapters/persistence/storage/master_key/` package except the inward key port. It also finds no tax-package module defining any of these: `authenticate_profile_for_invocation`, `authenticate_profile_candidate`, `_PROFILE_CONNECTION_KEYS`, `session_admission`, `ProfileWorkerCustody`, `ApprovalSession`, `login_throttle`, the KDF worker, or the receipt mint.

**DEK.**
- A test runs a CLI login, a CLI profile creation and a TUI registration against a real runtime.
- It asserts that each frontend process never imported the KDF supervision, envelope, receipt or worker-custody modules.
- It asserts that the only DEK-bearing frames are the KDF child's and the host-to-worker frame.

**Formats.**
- Records written by the code before the move are read back by the code after it, and the reverse.
- This covers an envelope, a recovery record, `session.v2.json` with its keychain entry, a throttle sidecar, a sign-in generation and an automation control record.
- The fixtures are the synthetic profiles of the existing custody tests. The roundtrip compares typed meaning and digests, not file names.

**Contract.**
- Each sign-in refusal reason reaches the CLI, the TUI and the desktop host command undiminished, through the real runtime.
- `throttled` carries its remaining seconds.
- A wrong password yields `credential_rejected` and advances the throttle.
- The throttle is evaluated before the KDF, clears on corrupt state, and is not cleared by logout.

**Parity.**
- The existing MCP parity, attendance, resume and key-admission suites in `dev/runtime_lifecycle/tests/` pass unchanged in behaviour.
- `dev/runtime_lifecycle/caller_owned_root.py` proves on a rebuilt package that sign-in through the CLI, the TUI and the desktop host command is followed by MCP resume, and that sign-out ends it.
- The CLI, the TUI and the MCP harness each resolve the active profile through the no-session query, and test cases cover all of these through a real runtime:
  - a signed-in profile;
  - a selected profile that is not signed in;
  - no profile;
  - an unknown state.
- A test with a pointer file that disagrees with the runtime's answer shows that every frontend follows the runtime.
- A filesystem search finds no pointer read or write in `src/cadrumo/entrypoints/`, `src/cadrumo_client/`, `src/cadrumo_harness/` or `src/cadrumo_runtime/commands/`.

**Runtime-free acts (once OD1 is confirmed).**
- With no runtime running, the five former in-process modes and `aeat config profile create` refuse with the client's typed unavailability.
- They write nothing.

**Regressions.**
- Each Step reports new failures separately from the triaged pre-existing failures of the worktree.
- Wide runs stay small and serial, coordinated with the live build session.
