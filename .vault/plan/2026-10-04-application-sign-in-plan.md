---
tags:
  - '#plan'
  - '#application-sign-in'
date: '2026-10-04'
tier: L2
related:
  - '[[2026-10-04-application-sign-in-adr]]'
modified: '2026-10-04'
body_schema: body-v2
body_hash: 'sha256:3bf5227212f3d44aeedab2ea88487db7257d75b963bc7b7a1c024ff1abdb18e2'
---

# `application-sign-in` plan

## Description

Approved 2026-10-04. Basis: the operator's "Approved! go" in response to the presentation of this plan and its sibling plan.

Implements `2026-10-04-application-sign-in-adr`, which the operator accepted on 2026-10-04.

Decision coverage: the accepted ADR governs every phase. Its amendments to the desktop-shell, runtime-manager, profile-access and custody ADRs are already applied. No new costly decision is needed for these steps.

The ADR names one follow-on decision: where the receipt-sealing key lives during idle extension. Until that is decided, receipts are not extended, and no step here implements extension.

Out of scope:
- **The desktop sign-in view and its host commands.** These belong to the desktop-shell plan. That plan starts once P01.S07, P01.S08 and P04 land, and receives this plan's stem and the commit for those steps.
- **Declaring `aeat` as a packaged entrypoint under `bin/`.** That belongs to the runtime packaging owner.

Platform scope:
- Sign-in is supported where login and lock state can be positively observed: Windows, and Linux with GNOME lock binding.
- Elsewhere it reports unavailable.

Ownership: runtime and client source under `src/cadrumo/**`, owned by this workstream. Locale strings go through the `dev.locales` workflow.

## Steps

### Phase `P01` - Runtime sign-in core

Runtime-owned shared sign-in: three-state lock observation, durable generation, bound receipt, ordered mint, proof-only borrowing, lock-down, global sign-out, status and typed refusals.

- [x] `P01.S01` - Report OS lock state as locked, unlocked or unknown in every login observer and make admission and lock-down consume the three states; `src/cadrumo/adapters/local_runtime/windows_login.py, linux_login.py, macos_login.py, login_policy.py, application/user_profile session authority consumers, owning tests`.
- [ ] `P01.S02` - Add the durable per-profile human sign-in generation record outside the encrypted bucket, fsynced before any receipt deletion, refusing resume when missing or unreadable, and register it in the storage taxonomy; `src/cadrumo/adapters/persistence/storage/custody/ new generation module beside automation_profile_lock.py, storage taxonomy owner, owning tests`.
- [ ] `P01.S03` - Bind the receipt to the originating login_id and sign-in generation under a new schema_version in session.v2.json, keeping the v2 keychain service and sending older schemas to the delete-only path; `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py, owning tests`.
- [ ] `P01.S04` - Mint the receipt only after session publication, under the admission guard, stamped with the generation captured at publication and discarded if the session is no longer published; `src/cadrumo/entrypoints/runtime/session_owner.py, profile_login.py, src/cadrumo/application/user_profile/session_authority_admission.py, owning tests`.
- [ ] `P01.S05` - Make receipt borrowing proof-only so clients read only the keychain proof and locator while the runtime verifies, unwraps and deletes; `src/cadrumo/adapters/local_runtime/frontend_client.py, acceleration_receipt.py, src/cadrumo/application/user_profile/login_session.py, owning tests`.
- [ ] `P01.S06` - Advance the generation and delete the receipt on lock everywhere, positive OS lock and logout evidence, password rotation or reset, recovery and profile deletion, and sweep receipts whose bound login is positively gone; `src/cadrumo/application/user_profile/session_authority_lifecycle.py, automation_lifecycle_service.py, src/cadrumo/entrypoints/runtime/profile_host.py, profile_connections.py, owning tests`.
- [ ] `P01.S07` - Add the runtime human_sign_out operation for human-kind sessions or a presented proof, retiring every human and attended session and reporting remaining automation; `src/cadrumo/application/runtime/ contracts and transport, src/cadrumo/entrypoints/runtime/, owning tests`.
- [ ] `P01.S08` - Add the unauthenticated sign_in_status runtime request reporting present, absent or unknown with deadlines, creating no worker and never reading the keychain; `src/cadrumo/application/runtime/ contracts, src/cadrumo/adapters/local_runtime/server dispatch, src/cadrumo/entrypoints/runtime/, owning tests`.
- [ ] `P01.S09` - Split typed refusals so THROTTLED carries remaining seconds and PROFILE_LOCKED, receipt reasons and generation changed reach clients, and add the throttle unreadable-state diagnostic while it keeps clearing; `src/cadrumo/entrypoints/runtime/profile_login.py, src/cadrumo/application/user_profile/access_contracts.py, src/cadrumo/adapters/persistence/storage/master_key/login_throttle.py, error catalogue, owning tests`.

### Phase `P02` - Session events

Pushed revocation events from a single reason-carrying retire point over a new event frame kind.

- [ ] `P02.S10` - Carry a reason through the session retire point, including lazy retirements, so every retirement is observable once; `src/cadrumo/application/user_profile/session_authority_core.py, src/cadrumo/entrypoints/runtime/profile_connection_sessions.py, owning tests`.
- [ ] `P02.S11` - Add the session event frame kind with client-side demultiplexing and a bounded non-blocking per-connection queue that emits after commit and closes the connection on overflow; `src/cadrumo/adapters/local_runtime/framing.py, server_connection_handling.py, runtime_client.py, frontend_client.py, owning tests`.

### Phase `P03` - Legacy retirement

Only the runtime owner mints, extends or deletes a receipt.

- [ ] `P03.S12` - Retire the registered in-process login and logout operations and the non-runtime CLI receipt extension, and add a gate test that no other code mutates receipts; `src/cadrumo/application/auth/operation_definitions.py, src/cadrumo/application/user_profile/operations.py, profile_operation_execution.py, session_admission.py, login_session.py, owning tests`.

### Phase `P04` - CLI

Interactive-only automatic resume, global sign-out and the status leaf.

- [ ] `P04.S13` - Gate automatic receipt resume on an interactive terminal and make config login without a secret refuse with passphrase_channel_absent when non-interactive; `src/cadrumo/entrypoints/cli/runtime_profile_admission.py, src/cadrumo/entrypoints/cli/config/custody.py, secure_input.py, owning tests`.
- [ ] `P04.S14` - Route config logout to the global human sign-out and add the config sign-in-status leaf with its result model, locale keys and regenerated CLI references; `src/cadrumo/entrypoints/cli/config/custody.py, config_payloads.py, command specs, src/cadrumo/locales/ via dev.locales, generated CLI reference, owning tests`.

### Phase `P05` - TUI

Resume first, opt-in persistence, event-driven clearing and global sign-out.

- [ ] `P05.S15` - Make the TUI resume a live sign-in first and offer a Stay signed in opt-in defaulting off on its password screen; `src/cadrumo/entrypoints/tui/secret/runtime_login_form.py, runtime_login_attempt.py, runtime_admission.py, locale keys, owning tests`.
- [ ] `P05.S16` - Subscribe the TUI to session events to clear private views immediately, route sign-out to the global operation and keep Lock this window; `src/cadrumo/entrypoints/tui/app.py, runtime_account.py, app_navigation.py, runtime_session.py, owning tests`.

### Phase `P06` - Acceptance and review

Cross-surface acceptance and integrated review against the ADR.

- [ ] `P06.S17` - Run the acceptance matrix for lock-down events against open TUI and CLI windows, sign-out racing resume, crash around mint, reboot, a Windows RDP or SSH second session, unknown lock state, upgrade with a live older receipt, keychain unavailability, throttling and non-interactive CLI; `runtime, CLI and TUI integration suites, disposable Windows host, feature audit`.
- [ ] `P06.S18` - Review the integrated sign-in model against the accepted ADR and its amendments and record findings; `feature audit`.

## Parallelization

P01 is ordered:
1. S01 (three-state lock) and S02 (generation) come first.
2. S03 through S06 depend on S02.
3. S07 through S09 depend on S02 and S03.

Other phases:
- P02 can run in parallel with P01 after S02. Its event frames carry the generation and lock-down reasons.
- P03 lands together with, or immediately after, S03 and S05, so that no legacy writer survives the new binding.
- P04 depends on S07 and S08.
- P05 depends on S05 and on P02.S11.
- P06 runs last.

Write ownership:
- Runtime and adapter modules: P01 to P03.
- `src/cadrumo/entrypoints/cli/`: P04.
- `src/cadrumo/entrypoints/tui/`: P05.

The worktree is shared, so commits are scoped by pathspec.

## Verification

**Per phase.** Focused tests through the real runtime, adapters and clients cover each of the following:
- **Generation and receipt.**
  - A missing or unreadable generation record refuses resume and deletes the receipt.
  - A receipt minted under an older generation or another `login_id` is refused.
  - A mint racing a sign-out leaves no live receipt.
  - Older-schema receipts go down the delete-only path.
- **Lock-down.**
  - Each lock-down event advances the generation before deleting the receipt.
  - Unknown lock state never deletes the sign-in.
- **Sign-out and status.**
  - `human_sign_out` retires every human and attended session and reports remaining automation, while API-key sessions are unaffected.
  - `sign_in_status` never creates a worker or touches the keychain.
- **Refusals.** Typed refusals reach the CLI and TUI uncollapsed, and the throttle still clears on corrupt state.
- **Session events.** Events reach every affected connection after commit, and queue overflow closes the connection.
- **Legacy paths.** A gate test proves no code outside the runtime owner mints, extends or deletes a receipt.
- **CLI.** Non-interactive invocations never auto-resume.
- **TUI.** It resumes first and clears views on an event.

**Every step:**
- The project's lint, format, type and import-boundary checks pass.
- The generated CLI reference and locale audits pass.
- `vault check all` passes.

**Completion:**
- The plan is complete when every step is closed and the integrated review at P06.S18 passes against the ADR.
- Phase-close reviews apply at L2.
- Platform limits are reported separately from code defects.
