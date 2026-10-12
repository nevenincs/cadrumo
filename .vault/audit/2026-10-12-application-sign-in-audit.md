---
tags:
  - '#audit'
  - '#application-sign-in'
date: '2026-10-12'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:c0d7caf0eaf7ef235ec7bb9b093acab09d4e0c3a6589ff3d795d0996537b61e8'
related:
  - "[[2026-10-04-application-sign-in-plan]]"
  - "[[2026-10-04-application-sign-in-adr]]"
---

# `application-sign-in` audit: `Integrated sign-in review`

## Scope

Integrated review P06.S18 of `2026-10-04-application-sign-in-plan` against `2026-10-04-application-sign-in-adr` with its 2026-10-06, 2026-10-09, 2026-10-10 and 2026-10-12 amendments (the 2026-10-12 parity wording read from the working tree, not yet committed), `2026-10-11-mcp-parity-full-parity-adr` and `2026-10-10-mcp-parity-shared-sign-in-door-adr`. Target: HEAD 73243999c3 on feature/tui plus the working tree. Commits read: 2d181b04da, 91e36da416, b2c84ddf91, 4193340fe8, ed7418e7b3, b04bcae09d (implementation) and b117395a09, d3458a30b7, f648f85f82, c0b3d06b1e, 5eaae73ee9, 8243c9a3ae, d46ff4c319, f9662e48bf, 03acd89702, 03ded1d112, 73243999c3 (2026-10-12 closures and fixes). Workflows traced across runtime, CLI, TUI and the MCP harness: password sign-in, resume on the TUI, the interactive CLI and MCP, the non-interactive refusal, global sign-out from any frontend, lock-down and generation advance, the orphan sweep, `sign_in_status`, session events, typed refusal rendering, and the receipt-ownership gate. Uncommitted work by another lane in `access_contracts.py`, `profile_host.py`, `login_policy.py` and `windows_login.py` (a `NOT_APPLICABLE` lock state for non-desktop logons) was read for its effect on lock-down only. Discovery ran without semantic search: the code index answered "updating", so targeted grep was used.

Verification evidence for this review: one focused run of 35 sign-in modules across runtime, adapters, custody, CLI, TUI and the MCP harness with `-m ''` and `-n 4` gave 633 passed and 2 failed (run log `var/storage/development/.logs/test-runs/2026-10-12/20261012T061913.414523Z-pytest-34288-61b438c9`). Of the two failures, `test_installed_cli_resumes_other_profile_without_retiring_original` passes alone and is explained under its finding. `test_the_person_locks_the_profile_and_resumes_it_with_the_password_from_every_frontend[tui]` failed with `runtime_deadline_exceeded` in three of four runs and passed once alone. Its `cli` and `mcp` parameters passed every time. Per-test times of 50 to 145 s point to a loaded host. Lint, format, type and locale evidence is reused from the ledger rows of S09, S12 to S15, which pass on each Step's own files. The repository-wide format, type and import-boundary gates were red on other lanes' files, and they were not rerun here. Native keychain (`os_keychain`) tests cannot pass in this SSH logon because Credential Manager refuses with WinError 1312. That is environmental, and their acceptance belongs to P06.S17.

Found sound:

- **Logout beats resume.** Sign-out advances the durable generation before deleting the receipt (`src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py:757`), under the host guard that is also the admission guard. It then bumps the in-memory admission generation (`src/cadrumo/application/user_profile/session_authority_lifecycle.py:47`). A resume compares that generation after worker authentication and again at publication (`src/cadrumo/application/user_profile/session_authority_admission.py:328`, `:400`). Publication, generation capture and mint happen under one guard hold (`:422`), so a sign-out cannot interleave.
- **Unknown lock never deletes a sign-in.** Lock-down and the sweep count only `LOCKED`, or an inactive login marked `INELIGIBLE`, as positive (`src/cadrumo/entrypoints/runtime/profile_host.py:562`, `src/cadrumo/entrypoints/runtime/sign_in_sweep.py:87`). The sweep skips a bound login it can see but whose lock state is uncertain, and it skips everything when the inventory is incomplete or custody is unreadable. The uncommitted `NOT_APPLICABLE` state keeps both rules.
- **The TUI resume-first fallback does not hide refusals.** It stays quiet only when it has no binding and the reason is `absent` or `keychain_entry_missing` (`src/cadrumo/entrypoints/tui/secret/runtime_login_attempt.py:39`, `:248`). Generation-changed and login-mismatch refusals carry a binding, so they are still shown, and so are expiry, custody, keyring, throttle and `PROFILE_LOCKED`.
- **The CLI refusal keys exist in all four locales** in the informal register: es "Ejecuta", ca "Executa", hu "Futtasd". A test covers every reason and binding pair in every language.
- **The CLI interactive gate holds.** A CLI not attached to a terminal never resumes (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:119`), and `config login` without a secret refuses with `passphrase_channel_absent`.
- **The runtime gives MCP the same sign-in model as the CLI.** Login dispatch reads only the method (`src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:96`). Global sign-out and locking another session check only the session kind (`:209`, `src/cadrumo/application/user_profile/session_authority_access.py:119`, `:200`). The MCP session tool offers `sign_in` by password, `store`, `sign_out`, `lock`, `sign_in_status` and `resume`. The only MCP-specific narrowing in an access path is the surface the person chooses (`src/cadrumo/application/user_profile/operation_access_policy.py:222`).
- **Session events reach every frontend.** Retirement events reach the TUI, the CLI notice subscription and MCP (`src/cadrumo_harness/mcp/runtime_adapter.py:284`).
- **The receipt-ownership gate pins each mutator name to its exact owning modules.** It fails on a stale allowance and catches four planted second owners.

Verdict: no critical or high finding. The review gate for P06.S18 passes. Plan completion stays PENDING on P06.S17.

## Findings

### mcp-sign-in-refusal-facts | medium | MCP replies drop the typed sign-in refusal facts that the CLI and TUI render

The MCP harness answers every refusal with `{"outcome": "refused", "code": ...}` (`src/cadrumo_harness/mcp/runtime_adapter.py:479`, `src/cadrumo_harness/mcp/protocol_contract.py:616`), and it keeps an admission denial only as a code string (`runtime_adapter.py:313`, `:330`). The runtime's `SignInRefusal` is therefore lost on MCP: a throttle's remaining seconds, the receipt reason, and a `generation_changed` or `login_mismatch` binding. A throttled password `sign_in` reads as `authentication_required`, and a sign-out elsewhere is indistinguishable from never having signed in. A refusal met before the runtime is asked collapses the same way (`src/cadrumo_harness/mcp/runtime_admission.py:129`). The 2026-10-12 parity amendment makes MCP a password sign-in surface, so the sign-in ADR's rule that typed refusals reach every sign-in surface uncollapsed, and constraint 3 of the parity ADR, now apply to it. The harness is outside this plan's write ownership (`src/cadrumo/**`), so no Step of this plan reopens.

### cli-config-tests-terminal-patch | medium | The S13 test's terminal declaration does not reach the admission module, so its positive control is order-dependent

`test_installed_cli_resumes_other_profile_without_retiring_original` patches `cadrumo.entrypoints.cli.config.secure_input.terminal_can_prompt_for_secrets` (`src/cadrumo/entrypoints/cli/config/tests/test_runtime_login.py:386`). `runtime_profile_admission` binds that name by a from-import at module load (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:44`, used at `:119`). Once another test has imported the module, the patch misses it. `config profile view` then refuses with `passphrase_channel_absent`, and the test fails under `-n 4` while it passes alone. The product gate is correct. The flaw is in the evidence: the interactive-resume positive control that S13 cites is order-dependent, and the same pattern sits in the other tests that 03acd89702 and 4262d73637 changed. Patch the name where it is used, or route the check through one attribute lookup. This belongs to S13 as a test fix and does not affect the product.

### door-tui-profile-lock-deadline | medium | Locking the profile from a TUI-frontend session timed out in three of four runs

`test_the_person_locks_the_profile_and_resumes_it_with_the_password_from_every_frontend[tui]` (`src/cadrumo/entrypoints/runtime/tests/test_mcp_sign_in_door.py:186`) raised `runtime_deadline_exceeded` while `deny_automation(PROFILE_LOCK)` waited 10 s for its reply. The reply wait is at `src/cadrumo/adapters/local_runtime/frontend_client.py:469`. The test then hit `TimeoutError` in fixture teardown (`stored_sign_in_runtime.py:289`). It failed under xdist, alone, and in a three-parameter run, and passed once alone in 146 s. Its `cli` and `mcp` parameters always passed. The runtime handler has no frontend branch (`src/cadrumo/entrypoints/runtime/access_management.py:132`), and the long timings point to host load, so a product defect is not established. Lock everywhere is a lock-down path of this plan, however, so the intermittent failure must be explained before the plan closes. The test came from 508d1c3fb0 (mcp-parity). Its owner should reproduce it on a quiet host. S17 also exercises lock everywhere from open TUI windows.

### cli-residual-refusal-messages | low | Several typed resume reasons still render the CLI's "session expired" message

`session_refusal_translation_key` sends every reason other than absent, keychain-entry-missing and custody-changed, when it carries no binding, to `profile_session_expired` (`src/cadrumo/entrypoints/cli/_profile_session_gate.py:50`). Those reasons include `tampered`, `malformed`, `schema_version_mismatch`, `generation_missing`, `generation_unreadable`, `generation_binding_mismatch`, `no_live_capsule`, and `keyring_unavailable` on the `raise_runtime_refusal` path. The context still carries `sign_in_reason`, so nothing is lost on the wire, but the message misstates the cause. An upgrade with an older receipt, for example, tells the person that their session expired.

### cli-logout-receipt-refusal | low | `config logout` renders a receipt refusal as a bare code and cannot sign out password-only sessions

The receipt-refusal branch raises `CliRefusedBoundaryError(str(error.reason))` with no translation key (`src/cadrumo/entrypoints/cli/config/custody.py:366`), outside S09's rendering. The client can prove itself for sign-out only through the receipt (`src/cadrumo/adapters/local_runtime/frontend_client.py:381`). With no saved receipt, for example a TUI signed in with Stay signed in off, `aeat config logout` refuses `absent` while human sessions stay live. The TUI's own sign-out covers that case, and the ADR admits only a session or a presented proof, so no authority is extended.

### receipt-gate-scope | low | The receipt-ownership gate scans only `src/cadrumo`

The gate walks `src/cadrumo` (`src/cadrumo/adapters/persistence/storage/custody/tests/test_receipt_mutation_ownership.py:22`, `:80`). It does not read the shipped MCP harness `src/cadrumo_harness`, and it matches names, so a dynamic import would pass. A grep today finds no receipt mutation in the harness. `dev/runtime_lifecycle` calls `delete_profile_session` for fixture cleanup, which is developer tooling, not product.

### login-mismatch-deletion | low | A same-account resume from another logon still deletes the stored sign-in

The worker deletes a receipt refused for `login_mismatch` once the proof unwraps (`src/cadrumo/entrypoints/runtime/profile_login.py:106`). Under the 2026-10-09 admission amendment, a same-account non-desktop logon such as SSH authenticates with its own logon. Its resume is therefore refused and signs the desktop person out everywhere. The door ADR left open whether a mismatched login should delete the sign-in at all, and no record settles it. This is not a defect against the current text, but the behaviour is untested on a host. It is an S17 item.

### s17-pending-acceptance | low | Pending verification: what P06.S17 must prove on a disposable Windows host

This is not a defect. P06.S17 must show, with an interactive desktop and a working Credential Manager:

- Lock everywhere, OS lock, OS logout, password rotation and reset, recovery and profile deletion each clear open TUI and CLI windows through events. Each advances the generation before deleting the receipt, and the TUI-frontend profile lock above is included.
- Sign-out racing resume leaves no live session or receipt.
- A crash before and after the mint leaves no orphan receipt and no usable stale one.
- After a reboot, the stored sign-in is refused or swept.
- An RDP or SSH second session of the same account behaves as the ADR says, including the login-mismatch deletion above.
- An unknown or not-applicable lock state never deletes the sign-in.
- An upgrade with a live older-schema receipt takes the delete-only path, with a message that is not "expired".
- When the keychain is unavailable, the CLI falls back to the password prompt or refuses typed, and the TUI shows its code.
- Throttling reports the remaining seconds on the CLI, the TUI and MCP.
- A non-interactive CLI never resumes.
- No receipt is mutated outside the runtime owner.
- The `os_keychain` tests pass. They cannot pass in this SSH logon (WinError 1312).

The desktop-secret item belongs to the desktop-shell plan.

## Recommendations

- **mcp-sign-in-refusal-facts.** Carry the public `SignInRefusal` fields in MCP refusal replies and in the stored admission denial, the way the CLI context does. This is mcp-parity work under its full-parity ADR and needs no new decision.
- **cli-config-tests-terminal-patch.** Patch the terminal check where `runtime_profile_admission` uses it, in every test that declares a terminal. This is a test-only fix within S13's scope.
- **door-tui-profile-lock-deadline.** Have the mcp-parity owner reproduce the failure on a quiet host. If it reproduces, trace the TUI-frontend profile-lock reply path. If it is load, widen the test's deadline for host load rather than the product's.
- **cli-residual-refusal-messages and cli-logout-receipt-refusal.** Route the logout branch through `session_refusal_translation_key`. Give the generation, tamper and schema reasons messages of their own, through `dev.locales` in all four locales. Optionally offer the password prompt to an interactive `config logout` when no receipt exists.
- **receipt-gate-scope.** Extend the gate's root set to `src/cadrumo_harness`.
- **login-mismatch-deletion.** Before S17 closes, the owner of the per-session admission follow-on must decide whether a mismatched logon deletes the stored sign-in or only refuses it.
