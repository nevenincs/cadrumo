---
tags:
  - '#adr'
  - '#runtime-authority-boundary'
date: '2026-10-18'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:d191e44f408ede73074773bb74356cc90d8dfcc97877ad664a0afd19bc9ea27b'
related:
  - "[[2026-10-18-runtime-authority-boundary-reference]]"
  - "[[2026-07-01-import-centralization-adr]]"
  - "[[2026-08-13-profile-session-lifecycle-successor-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-13-profile-state-aggregate-successor-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-12-mcp-parity-attended-live-sign-in-adr]]"
  - "[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
---

# `runtime-authority-boundary` adr: `Runtime owns login, session, lease and custody authority` | (**status:** `accepted`)

## Problem Statement

On 2026-10-18 the user ruled, verbatim: "be careful not to conflate runtime a higher level construct with the cli tui mcp. those require a runtime but do not manage them. ensure there's no runtime management code in the cadrumo/ src".

Rule 00 already assigns process hosting, native peer admission, login state, session authority and authentication administration to `src/cadrumo_runtime`. The code does not match. `2026-10-18-runtime-authority-boundary-reference` records two large, pre-existing departures:

- **Frontends authenticate.** The CLI keeps an in-process login that runs the KDF, the throttle and the DEK binding in the CLI process. The CLI and the TUI also create profiles, enrol recovery and rotate passwords in their own processes (findings A and C).
- **Authority lives in the tax package.** The runtime's login, lease, worker-custody, receipt, throttle, KDF and automation-access machinery is defined under `src/cadrumo` and imported by the runtime (finding B). Its wire shapes are defined there too (finding D).

This record decides where that authority lives, the contract through which frontends reach it, and the order of the move.

## Considerations

- The runtime already owns the protocol: login request, secret frame, session authority, worker custody and receipt mint (reference, Summary). What remains in `src/cadrumo` is mostly the building blocks the runtime calls, plus one parallel in-process door.
- Only four CLI leaves and one preview mode still take the in-process route. Every other profile-bound leaf already reaches the runtime (reference, finding A).
- The tax application may not import the runtime (`.importlinter:220-227`). Anything that stays in `src/cadrumo` and still uses a moved module must move with it, or be deleted first.
- The runtime composes the tax application through its public defining modules (rule 00). The runtime may therefore keep importing tax-owned profile records, discovery, storage taxonomy and operation definitions.
- `2026-07-01-import-centralization-adr` requires atomic moves (definition, tests, consumers and metadata together) with no aliases. Its 2026-10-15 correction keeps frontends in `cadrumo.entrypoints`.
- Persisted custody formats, keychain names and lifetimes are settled by `2026-08-13-profile-password-custody-rollup-adr` and `2026-10-04-application-sign-in-adr`. Moving code must not change a byte of them.
- The in-flight `2026-10-18-dependency-provisioning-plan` and a parallel boundary-fix workstream own files this work would otherwise touch.

## Considered options

- **Leave the building blocks in `src/cadrumo` and delete only the in-process door.** Rejected. The user ruled that no runtime management code remains in `cadrumo/`. Worker custody, leases bound to the runtime boot, throttle and receipts are runtime management by rule 00's own list.
- **Move every `user_profile` and storage module that mentions a session.** Rejected. It would move tax facts, profile records, discovery and tax persistence encryption into the runtime, which is the conflation the ruling forbids in the other direction.
- **Classify by responsibility: authority moves to the runtime, wire shapes move to the client contracts, tax facts and presentation stay.** Chosen.
- **Keep wire shapes in `src/cadrumo` and let the client import them.** Rejected for authentication shapes. Frontends and the runtime would depend on the tax package for the very protocol that separates them. The client's other imports of the tax package are outside this decision (Consequences).

## Constraints

### Target ownership

**`src/cadrumo_runtime` owns all of the following:**

- password, recovery, receipt and API-key proof, and the supervised KDF child that serves it;
- DEK generation, wrap, unwrap, binding, lease-scoped lending and zeroisation;
- the custody envelope, sentinel proof, recovery record and capsule publication transactions: create, restore, delete, password rotation and reset, recovery enrol, rotate and remove;
- the failed-attempt throttle;
- the human acceleration receipt, its keychain entry and sealing key, and the sign-in generation;
- human, attended and API-key sessions, access leases, worker custody, and their binding to the runtime boot and native connection;
- automation grants, enrolment, approval, the control store and native credential-store policy;
- access-administration policy;
- login-target resolution for an authentication request;
- the active-profile pointer: its writes, and the answer to "which profile is selected or signed in" for every frontend;
- session events.

**`src/cadrumo_client/contracts` owns the wire shapes:**

- the login request, admitted status and refusal envelope;
- one closed sign-in refusal set;
- the access denial and automation custody codes that cross the wire;
- the operation-declaration access vocabulary (actions, disclosure categories and permissions, scopes, operation access policy), which tax operation definitions declare and the runtime evaluates;
- the receipt locator and keychain naming that a frontend needs to present a proof;
- the installation act requests, including a new profile-creation act;
- the no-session active-profile query and its reply.

**`src/cadrumo_client/transport` owns proof presentation:** frame I/O, secret frames, and reading the keychain-held receipt proof for presentation. *Hypothesis:* the neutral native credential-store primitive also lives here, so that the frontend's proof read and the runtime's writes share one implementation without the tax package owning it.

**`src/cadrumo` keeps the following, each because it is tax product or presentation, not authority:**

- **The doors.** `aeat config login`, `aeat config logout`, `aeat config profile create`, and the TUI's login, registration, recovery and password screens. Each prompts or reads its secret channel, opens the verified client, presents the secret and renders the typed outcome. A door decides nothing about authentication.
- **Tax operation definitions**, which declare their access needs in the client-contract vocabulary.
- **Profile records.** The semantic profile record repository, profile facts, projections, overview and censal work.
- **Non-secret profile discovery and listing**, which needs no password, session or runtime under `2026-10-04-application-sign-in-adr`.
- **Tax persistence encryption.** Encrypted columns, secure objects and blobs consume key material only through an inward port that `src/cadrumo` defines and the runtime binds.
- **Storage taxonomy declarations**, including the locations of runtime-owned records. Under the 2026-10-15 correction in `2026-07-01-import-centralization-adr`, a shared layout declaration may name a consumer without granting its authority.
- **Provider authentication.** AEAT certificate and Cl@ve sessions and Google authorization are provider sessions, not runtime login, and are out of scope.
- **The portable bundle passphrase encryption**, which is a tax export.

### Deleted as duplicates, not moved

- The in-process admission: `session_admission.py` and `authenticate_profile_for_invocation`.
- The in-process branch of the CLI gates: the credential path of `_resume_or_authenticate`, `consume_root_fallback`, `prompt_root_authentication` and `_authenticate_for_invocation`.
- The settings passphrase fallback.
- Frontend-process session publication at creation (`publish_created_profile_session`).
- Route selection by `_PROFILE_CONNECTION_KEYS`. Every profile-bound leaf presents through the runtime, so the set has no remaining role.
- One of the two profile-admission doors. `src/cadrumo_client/commands/profile_admission.py` and `src/cadrumo_runtime/commands/profile_admission.py` become one client-side door used by both executables.
- Duplicated lease checks in tax code, once the runtime's checks are shown to cover them. The overlap is unverified (reference, Duplication), so each deletion first proves equivalence in a test.

### Client contract

- **Presenting a secret.** A frontend opens a verified connection, sends one typed request and waits for `SecretReady`. The request is either `ProfileLogin` (with `password`, `receipt` or `api_key`) or an installation act that needs a secret. The frontend writes the secret once as a bounded `S` frame, wipes its mutable buffer, and keeps no secret after presentation. The secret never travels in a document frame, argv, environment, log or result.
- **The outcome.** The runtime answers with an admitted status or a typed refusal. The sign-in refusal set is closed:
  - `throttled`, with remaining seconds
  - `profile_locked`
  - `receipt_expired`
  - `receipt_absent`
  - `custody_changed`
  - `keyring_unavailable`
  - `login_mismatch`
  - `generation_changed`
  - `credential_rejected` (new: a wrong password stops being a generic automation custody code)
  - `passphrase_channel_absent`

  Runtime unavailability is the client's typed connection result. No surface collapses or rewrites a reason.
- **Throttle.** Throttle state lives only in the runtime. It is evaluated before the KDF and clears on missing or corrupt state. Otherwise it clears only on a successful proof or when its wait expires. A frontend learns only the reason and the remaining seconds.
- **Login target.** A frontend sends the operator's profile name or UUID. The runtime resolves and validates it, so no frontend imports the login-target resolver for authentication.
- **Active profile.** A new no-session runtime request tells a client which profile holds the live sign-in, and which profile is selected (reference, finding F).
  - It is answered on a verified connection that holds no session. It opens no worker and reads no keychain, like `sign_in_status`.
  - Its reply carries the signed-in profile id or none, the selected profile id or none, and a presence of `present`, `absent` or `unknown`.
  - It may ask for the existing `sign_in_changed` cue, so a watcher re-reads instead of polling.
  - The reply grants nothing: admission still requires presenting a proof, a held sign-in's approval, or a configured key.
  - *Hypotheses:* the request name, and whether it extends `SignInStatusRequest` with an optional profile or is a separate request.
- **Pointer ownership.** The runtime is the pointer's only writer. It selects a profile after a successful login, at profile creation, and as logout and deletion require.
  - No frontend (CLI, TUI, desktop host, MCP harness, client commands, or the runtime's own CLI commands) reads or writes the pointer file. Each asks the runtime.
  - Inside the profile worker, tax code that needs "the current profile" uses the worker's bound profile, never the pointer.
  - The tax package keeps no pointer writer.

### DEK and custody invariants

- The DEK exists only in runtime-owned processes: transiently in the runtime host, in the profile worker, and in their supervised KDF child.
- The DEK never exists in a frontend process (CLI, TUI, desktop, MCP server, agent service), in a client-facing frame, on disk unwrapped, or in logs, argv or environment.
- No module under `src/cadrumo` generates, wraps, unwraps, binds, extends, persists, transmits or retires a DEK, receipt key, sealing key or automation wrap key.
- In the worker, tax persistence reads key material only through the inward port. The port confers no lifecycle: no install, extend, share or close.
- Two crossings exist today: the KDF child's frames, and the host-to-worker secret frame after an automation unwrap. Both are kept, and no new crossing is added.
- The receipt-sealing key stays beside the DEK in worker memory.
- Persisted bytes do not change: envelope v1, recovery v1, `session.v2.json`, the keychain services and accounts, the throttle sidecar, the sign-in generation record and the automation control store. A move is a code move, never a format migration.

### Parity

- The CLI, the TUI and the desktop's host commands present the same requests and render the same refusals. Password prompting stays terminal-only.
- All three frontends learn the active profile from the same runtime query, never from the pointer file.
- MCP still carries no secret. It is admitted in one of three ways, as `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` and `2026-10-12-mcp-parity-attended-live-sign-in-adr` rule:
  - by resuming the live sign-in;
  - by attendance to a held sign-in;
  - by a key the person configured by reference in its launch configuration.

  Two things change for MCP. The harness imports the wire shapes from the client contracts. And it names the profile to resume or attend from the runtime's active-profile answer, keeping its existing refusal when that answer differs from the profile it is bound to.

### Ordering and coordination

- The order is:
  1. contracts;
  2. runtime doors;
  3. frontend door cutover;
  4. deletion of in-process authentication;
  5. relocation of the application services;
  6. relocation of the adapters;
  7. enforcement.
- Each move is atomic under `2026-07-01-import-centralization-adr`.
- Some files are owned by `2026-10-18-dependency-provisioning-plan`: `_PROFILE_CONNECTION_KEYS`, the TUI navigation registration and `src/cadrumo_mcp/mcp/`. Work touching them waits for the owning lane, or coordinates through its orchestrator.
- The same applies to the parallel boundary-fix workstream's files: `reset_cli`, `operation_installation`, `storage_materialization`, the MCP service's `runtime_admission`, and `.importlinter`.

### Open decisions, outside the accepted scope

- **OD1. No runtime-free profile act.** The question is whether these acts stop working with no running runtime and refuse with the client's typed unavailability instead:
  - the four in-process leaves and the censo preview;
  - `aeat config profile create`;
  - TUI first-run registration;
  - recovery enrolment and password rotation from a frontend;
  - the selected flag of the desktop's profile list. Labels stay runtime-free. With no runtime, the flag is reported as unavailable, never read from the pointer file.

  *Recommendation: confirm.* Rule 04 already makes clients connect-only. The tax package may not import the runtime, so a runtime-free login could survive only by keeping authority in `src/cadrumo`, which the ruling forbids. The in-flight plans' desktop and acceptance paths already start a supervised runtime.

  Until OD1 is answered, additive work proceeds: contracts, new runtime acts, and routing the five modes through the runtime. Removing each runtime-free path, and the relocations that depend on that removal, wait.
- **OD2. The rest of the runtime-hosted frontend.** The TUI and CLI frontend code under `src/cadrumo_runtime/host/frontend/` (67 modules) contradicts the 2026-10-15 correction.

  The accepted scope moves only the login and secret screens to `cadrumo.entrypoints.tui`, because this decision needs them to present through the client.

  *Recommendation: fold the rest into a follow-on phase of the same plan rather than a new decision*, since the correction already decides it.

## Implementation

We will:
- move every runtime-authority responsibility listed above into `src/cadrumo_runtime`;
- move its wire shapes into `src/cadrumo_client/contracts`;
- delete the duplicated in-process doors;
- leave `src/cadrumo` with presentation, tax facts and a consumer-side key port.

`2026-10-18-runtime-authority-boundary-plan` sequences the work.

- **Contracts first.**
  - The new client-contract modules take `sign_in_refusals.py`, the frontend-visible parts of `login_session.py` and `automation_custody_port.py`, and the declaration vocabulary of `access_contracts.py`.
  - The runtime records in `access_contracts.py` move with the runtime services, not to the client. These are grants, key records, sessions, eligibility, evaluation context and the lease maximum.
- **Runtime doors.**
  - Add a profile-creation installation act, so that creation runs in the runtime.
  - Confirm that rotation, recovery enrolment and removal, and reset are served as runtime acts. Add any that run in a frontend today.
  - Accept the operator's profile name in authentication requests.
  - Serve the active-profile query, and write the pointer from the runtime's login, creation, logout and deletion paths.
- **Frontend cutover.**
  - The CLI gates, the client commands, the runtime's own CLI commands and the MCP harness replace every pointer read with the active-profile query.
  - Tax code that reads the pointer is classified per call. A worker-side reader moves to the worker's bound profile. A frontend-side reader moves to the query.
  - The CLI routes the five in-process modes through registered runtime-hosted operations.
  - The CLI and the TUI send creation, recovery and rotation as runtime acts.
  - The TUI login and secret screens move into `cadrumo.entrypoints.tui`.
- **Relocation, application layer.** These move under `cadrumo_runtime.application`:
  - `login_session`, `login_session_port`, `login_interaction`, `session_retirement` and `authentication`;
  - `access_administration`, `access_policy` and `access_projections`;
  - the `automation_*` modules;
  - the `custody_*` services, `passphrase_rotation`, `prospective_password`, and `recovery_custody` with its operations;
  - the custody part of `registration`, `capsule_restore` and `capsule_archive`.
- **Relocation, adapter layer.** These move under `cadrumo_runtime.adapters`:
  - `master_key/*`, except the consumer-side key accessor, which becomes the inward port;
  - the KDF, envelope, recovery, sentinel, receipt, sign-in generation, automation and native keychain modules of `custody/`;
  - `profile_login_session.py` and `profile_custody.py`.
- **What stays for both packages:** non-secret discovery (`capsule_discovery`, label heads, paths, digest models, filesystem primitives) and `zeroise`.
- **Names are hypotheses.** Module names inside the runtime may change. The responsibility split is binding.
- **Enforcement uses Import Linter alone**, as `2026-09-26-mcp-purpose-authentication-profile-access-adr` requires:
  - A forbidden contract stops `cadrumo` from importing `keyring` and the native credential-store bindings. `argon2` stays permitted for the bundle passphrase.
  - The moved packages cease to exist under `cadrumo`.
  - A planted-defect test proves the contract fails.
  - The receipt-ownership gate and the import-load metadata follow the moved paths.

## Rationale

The ruling makes placement a matter of responsibility, not of who calls what. Rule 00 already lists the runtime's responsibilities, and every module in finding B serves one of them. Left in `src/cadrumo`, they keep the tax package as the de facto authority even though only the runtime runs them.

Deleting the in-process door, rather than moving it, follows from the import contract. Once authority lives in the runtime, the tax package can reach it only through the client, which is exactly what the other 248 leaves already do.

Putting the wire shapes in the client contracts gives the frontends and the runtime one protocol vocabulary that neither owns as authority. Keeping tax facts, discovery and the consumer key port in `src/cadrumo` avoids the reverse conflation.

## Consequences

**Benefits:**

- Authentication, custody and session policy have one owner and one implementation.
- No frontend process holds a DEK.
- The import contract turns a regression into a build failure.
- The CLI gate shrinks to channel selection and presentation.

**Accepted costs:**

- A large atomic move. It touches about 120 test modules, the runtime's roughly 315 imports of tax authentication and custody modules, and the import-load metadata.
- Once OD1 is confirmed, profile creation and the five modes depend on a running runtime.
- Tests that unlocked in-process need runtime fixtures, or a synthetic key bound through the inward port.
- Rules 02 and 05 cite custody locators under `src/cadrumo` that will move. Their text belongs to the user, so corrected locators are proposed, not applied.

**Out of scope:** about 98 `cadrumo_client` modules import the tax package for subjects other than authentication. That dependency direction is a separate question.

**Reconsider if:**

- a responsibility listed for the runtime proves necessary to a frontend that has no runtime connection;
- the inward key port cannot serve tax persistence without exposing lifecycle.

**Acceptance.** Accepted 2026-10-18 on the user's ruling quoted under Problem Statement, which directed this outcome; this record decides how. Acceptance records decision authority, not implementation. OD1 and OD2 remain open.

## Amendments to other records

Each amendment is applied in the named record as a dated section that keeps the earlier wording verbatim.

- **`2026-08-13-profile-session-lifecycle-successor-adr`.**
  - Old: "One application service owns active-session observation, explicit close, inactivity events, process shutdown cleanup, and operator-safe status projection."
  - New: that owner is the runtime's lifecycle service in `src/cadrumo_runtime`, and entrypoints reach it only through the client contract.
- **`2026-08-13-profile-password-custody-rollup-adr`.**
  - Old: "This protocol is enforced at the application enrollment boundary".
  - New: the password envelope, KDF supervision, recovery, capsule transactions, throttle and receipts are implemented and enforced in `src/cadrumo_runtime`. Every Argon2 child is spawned only by a runtime-owned process. Formats and rules are unchanged.
- **`2026-08-13-profile-state-aggregate-successor-adr`.**
  - Old: "`ProfileLifecycleService` is the sole physical lifecycle writer."
  - New: it is hosted in the runtime. `ProfileRecordRepository` stays tax-owned and receives its key through the inward port.
- **`2026-10-04-application-sign-in-adr`.**
  - Old: the Lifetime locators under `src/cadrumo/adapters/persistence/storage/...`, and the CLI line "the legacy in-process paths are retired".
  - New: the locators move with the code, and this record completes that retirement. The desktop profile list stays runtime-free. Profile creation from the desktop runs through the runtime act.
- **`2026-09-26-mcp-purpose-authentication-adr`.**
  - Old: "Profile-session and admitted-work inspection remain application capabilities."
  - New: profile-session authority is the runtime's. Admitted-work inspection remains an application capability.
- **`2026-09-26-mcp-purpose-authentication-profile-access-adr`.**
  - Old: the 2026-10-14 sentence "AEAT retains direct human profile login, logout and creation".
  - New: AEAT retains those doors, and their authentication and custody run in the runtime. The "one serialized application owner" of control updates is the runtime.
- **`2026-10-12-mcp-parity-attended-live-sign-in-adr`.**
  - Old: "Direct `aeat config login`, `aeat config logout` and profile creation remain tax commands."
  - New: they remain tax doors that present to the runtime.
- **`2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`.**
  - Old (constraint 2): "by resuming the person's live sign-in for the active profile, through the runtime".
  - New: "the active profile" is the profile the runtime names in its no-session active-profile answer. The MCP server never resolves it from the pointer file or any other local record. Constraint 5's binding to one profile for the server's life, and its refusal when the signed-in profile later differs, are unchanged.
- **No change, with the reason recorded here:**
  - `2026-07-01-import-centralization-adr`: this record executes its 2026-10-15 correction.
  - `2026-10-04-runtime-manager-architecture-adr`: the manager holds no authority either way.
  - `2026-10-10-mcp-parity-shared-sign-in-door-adr`: "No surface keeps login state" already holds.

## Package rename note 2026-10-21

(Locators as observed on their original dates; the MCP package was renamed from `cadrumo_harness` to `cadrumo_mcp` on 2026-10-21, drift repair toward cadrumo-agent `2026-10-15-agent-harness-adr`, authorized by the user in session TUI-REFACTOR. See the harness boundary amendment of `2026-07-02-agent-harness-refoundation-adr`. No commitment of this record changes.)
