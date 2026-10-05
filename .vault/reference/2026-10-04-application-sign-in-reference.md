---
tags:
  - '#reference'
  - '#application-sign-in'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:49a71ac9ca7863968a45d993e2190d57a08e2bc6063735e9b268d1633e9a837d'
related:
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-13-profile-session-lifecycle-successor-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
---

# `application-sign-in` reference: `Application sign-in state model`

Static enumeration of the human authentication and session state that the CLI, TUI and runtime hold today, and of how that state moves on login, logout, lock-down and OS events. It was gathered on 2026-10-04 at `feature/tui` `910b81398f` by an independent reviewer through targeted reads and grep. No tests were run, and semantic search was not used.

"Enforced" means a code path implements the behaviour. "Documented" means it appears only in a docstring or an ADR.

Path abbreviations:
- `LS` = `src/cadrumo/application/user_profile/login_session.py`
- `AR` = `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`
- `FC` = `src/cadrumo/adapters/local_runtime/frontend_client.py`
- `PL` = `src/cadrumo/entrypoints/runtime/profile_login.py`
- `SO` = `src/cadrumo/entrypoints/runtime/session_owner.py`
- `PH` = `src/cadrumo/entrypoints/runtime/profile_host.py`
- `PCA` = `src/cadrumo/entrypoints/runtime/profile_connection_admission.py`
- `PCS` = `src/cadrumo/entrypoints/runtime/profile_connection_sessions.py`
- `PC` = `src/cadrumo/entrypoints/runtime/profile_connections.py`
- `SAA`, `SAC`, `SAP`, `SAL` = `src/cadrumo/application/user_profile/session_authority_{admission,core,policy,lifecycle}.py`
- `ALS` = `src/cadrumo/application/user_profile/automation_lifecycle_service.py`
- `CC` = `src/cadrumo/entrypoints/cli/config/custody.py`
- `RPA` = `src/cadrumo/entrypoints/cli/runtime_profile_admission.py`
- `TA` = `src/cadrumo/entrypoints/tui/app.py`
- `TRA` = `src/cadrumo/entrypoints/tui/runtime_account.py`
- `TLF` = `src/cadrumo/entrypoints/tui/secret/runtime_login_form.py`
- `WL` = `src/cadrumo/adapters/local_runtime/windows_login.py`
- `PWC` = `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`
- `LT` = `src/cadrumo/adapters/persistence/storage/master_key/login_throttle.py`

## Summary

### State that exists today

All of this is enforced unless marked otherwise.

- **Unlocked DEK.** It lives in the profile worker as one process-wide `BucketSession` shared by all of the profile's leases (`PWC:191-218`). It is retired when the last lease goes (`PWC:173-189`) and does not survive a runtime restart. A candidate DEK from a password or receipt proof is held for at most 5 minutes (`PL:39-80`).
- **Human sessions.**
  - They are runtime memory (`SAC:50`), one per connection. The deadline is fixed at login as the minimum of the idle and absolute deadlines (`SAA:334-361`).
  - The runtime never extends a human session (`SAA:406-407`).
  - They end on:
    - disconnect (`PCS:268-281`)
    - the connection's own lock (`FC:243-258`)
    - profile lock (`SAL:40-57`)
    - OS lock or an inactive login (`SAC:85-97`, `SAP:297-315`)
    - a change of boot id (`SAP:66-67`)
    - a custody change (`PC:171-176`)
    - clock rollback (`SAC:62-64`)
- **API-key sessions.** At most 5 minutes, clipped to the grant and key (`SAA:169`). They are extended only by explicit `session_refresh` (`SAA:382-398`). They survive an OS lock only under `allow_os_lock` (`SAP:153-154`). Attended child sessions are clipped to their parent and cascade with it (`SAA:497-505`, `SAC:178-197`).
- **Captured login.**
  - Each connection captures a `login_id` (`PCA:157-161,184`). On Windows it is the runtime desktop's auth LUID, session and logon time (`WL:37-40,69-108`). Same-account peers from any session bind to the runtime's desktop.
  - `_logins` is not pruned on disconnect (`PCS:280-281`).
- **Human login receipt.**
  - Stored as `<root>/keystore/<id>/session.v2.json` plus a retirement journal (`AR:349-364`). The keychain key sits under service `cadrumo:profile-session:v2`, account `profile:session` (`AR:105,206-208`).
  - Deadlines are 15 minutes idle and 240 minutes absolute (`src/cadrumo/core/config_runtime_fields.py:234-242`, `AR:790-791`).
  - The AAD binds profile, session id, custody generation, DEK epoch and deadlines (`AR:16-21`). It does **not** bind the originating `login_id`, the runtime boot or any sign-in generation.
  - It is minted in the worker's `bind_human` when `persist_receipt` is set (`PL:114`, `LS:1015-1033`, `SO:281-296`). That happens before the lease is published (`SAA:363-380`).
  - Only the legacy in-process path extends it (`LS:586-599,736-769`, `AR:1242-1297`); the runtime resume path never does (`AR:1196-1198`).
  - The **client process** deletes it on expiry or custody change during a borrow (`AR:1169-1179,1322`), and the client unwraps the DEK during the borrow (`AR:1313-1337`).
  - It survives client exit, runtime restart, OS lock, OS logout and reboot until it expires.
- **Grants, AEAT session, throttle, pointer.**
  - API grants and keys are durable, 365 days by default.
  - The AEAT authority session is an encrypted row inside the bucket with an 18-minute idle limit (`src/cadrumo/application/auth/sessions.py:229-243`, `src/cadrumo/adapters/outbound/aeat/auth/authenticator.py:109`). It is unusable without an unlocked profile.
  - The login throttle is a sidecar under the keystore with backoff min(2^n, 60) s (`LT:102-118`). An unreadable sidecar counts as cleared (`LT:121-141`).
  - The active-profile pointer is a hint only (`CC:217-221`).
  - Lock everywhere persists `profile-lock.json` bound to custody, plus an in-memory fence (`src/cadrumo/adapters/persistence/storage/custody/automation_profile_lock.py:33-40`, `PH:466-489`).
- **Clients.**
  - The TUI polls `session_status` every 30 s (`TA:79,312-339`), every 10 s in the API-key shell (`src/cadrumo/entrypoints/tui/runtime_session.py:29`). Status never extends a deadline (`FC:223-225`).
  - The TUI offers receipt resume only as a login method the user picks by hand. It defaults to password and never mints a receipt (`TLF:51-53,82`, `src/cadrumo/entrypoints/tui/secret/runtime_login_attempt.py:76-85`).
  - The CLI's runtime route resumes first, otherwise uses the password without minting (`RPA:104-139`). Its non-runtime route still holds the DEK in the CLI process and extends the receipt (`src/cadrumo/application/user_profile/session_admission.py:173-186`).

### Transitions that matter for a shared sign-in

- **`config login`.** Resumes first; otherwise uses the password and mints the receipt, then sets the pointer (`CC:191-230`). Only CLI and TUI frontends may persist a receipt (`PCA:134-138`).
- **Logout and sign-out leave the receipt.**
  - `config logout` clears the pointer only and states that access remains (`CC:286-337`).
  - TUI sign-out locks only its own lease (`TRA:58-68,111-115`).
- **Lock everywhere** increments the lock generation, retires all leases and persists (`SAL:40-57`, `ALS:113-138`). It leaves the receipt in place, so after one password resume the receipt is resumable again. Other TUIs notice within 30 s.
- **OS events.**
  - OS lock retires human leases and refuses human admission while locked (`SAC:85-97`, `PCA:174`). The receipt is kept, so unlocking resumes silently.
  - OS logout stops the runtime once no eligible witness remains (`PC:122-128`). The receipt is kept and is resumable from the next login.
- **Credential changes.**
  - Password rotation or reset, and recovery, change the custody generation and retire the host (`PH:517-571`). That makes the receipt cryptographically useless (`AR:926-927`); it is deleted at the next borrow.
  - Profile deletion removes the receipt and the throttle (`LS:493-514`).
- **Restart and keychain failure.**
  - A runtime restart voids leases, but the receipt survives. A crash mid-login can therefore leave an orphan receipt.
  - With the keychain unavailable, minting reports not persisted (`LS:1762-1769`, `CC:139-147`) and resume refuses (`RPA:126-130`). Deletion still removes the disk half (`AR:672-681`).
- **Refusals and frontends.**
  - Throttle errors collapse into `CREDENTIAL_REJECTED` (`PL:57-59`), and no throttled code exists (`src/cadrumo/application/user_profile/access_contracts.py:377-413`). Receipt refusal reasons are collapsed too (`PL:81-88`).
  - The frontend enum has only CLI, MCP and TUI (`src/cadrumo/application/operations/registry.py:213-225`).
- **Push events.** None exist. Clients learn of revocation only by polling.

### Gaps, ranked

1. **Critical.** No user-reachable runtime revocation of the receipt (`CC:286-337`, `TRA:58-68`, `ALS:106-138`).
2. **Critical.** The receipt is not bound to the originating OS login, so it survives logout and reboot (`AR:123-138`).
3. **High.** The receipt is minted before the lease is published (`SO:294-296` against `SAA:363-380`).
4. **High.** Frontends read the keychain, unwrap the DEK and delete receipts (`FC:173-178`, `AR:1139-1182,1313-1337`). This contradicts `2026-08-13-profile-session-lifecycle-successor-adr`.
5. **High.** Human sessions and receipts are never extended on the runtime path (`SAA:359,406-407`, `AR:1196-1198`), while the legacy path extends from the frontend (`LS:594-599`).
6. **High.** No pushed session events. Private views can stay visible for up to 30 s after revocation (`TA:79`).
7. **Medium-high.** No sign-in generation fences a logout that races a resume.
8. **Medium.** Throttle and receipt refusals are collapsed, and the throttle fails open.
9. **Medium.** No desktop frontend identity exists, and `2026-10-04-desktop-shell-adr` forbids authentication UI and carrying receipts.
10. **Medium.** Legacy in-process logout and login operations are still registered (`src/cadrumo/application/user_profile/profile_operation_execution.py:478-496`, `src/cadrumo/application/auth/operation_definitions.py:203-215`). They could wipe the shared DEK or replace the receipt. Reachability is unverified.
11. **Low-medium.** The TUI never tries a receipt automatically.
12. **Low.** `_logins` is not pruned (`PCA:184`).
13. **Low.** `2026-08-13-profile-password-custody-rollup-adr` names service `v1` with a profile-UUID account, while the code uses `v2` with `profile:session`.
14. **Decision needed.** Sign-out and lock-down leave AEAT sessions in place (`src/cadrumo/application/auth/operator.py:872`).
