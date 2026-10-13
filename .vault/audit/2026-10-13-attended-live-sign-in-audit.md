---
tags:
  - '#audit'
  - '#attended-live-sign-in'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:475d993e4948264ca822198b104540e5fb42d51d01f61e2d011f77ef864e5a3d'
related:
  - "[[2026-10-12-attended-live-sign-in-plan]]"
  - "[[2026-10-12-mcp-parity-attended-live-sign-in-adr]]"
---

# `attended-live-sign-in` audit: `Plan-close review`

## Scope

Plan-close review of `2026-10-12-attended-live-sign-in-plan`, Steps S01 to S05, against `2026-10-12-mcp-parity-attended-live-sign-in-adr` and its Amendments, by an independent read-only reviewer on 2026-10-13. Commits 6521d4c2ca, fa4f7dc9c5, dd67b12273, 9274fb2240, e11fb302f2 and 9790b9e63c; S01 to S03 code arrived in c7fbea9454. The acceptance evidence is the packaged proof `just verify-live-sign-in` on manifest ec2e4fac443201e94e0b4c714328b8214db3e3f8ec36053af18c5730311d4e38, which exited 0 with expiry and the reviewed local-model step. The `test_attendance.py` integration tests run on a synthetic OS login and are not acceptance evidence. The reviewer ran `ruff check` on the six touched modules, which was clean; ty and pytest were not rerun because no input changed since the per-Step passes. Verdict: pass with findings. Nothing is critical or high, and no Step reopens.

The four operator constraints hold in code. No MCP sign-in or `session` tool exists, and the ask carries no secret (`src/cadrumo_harness/mcp/runtime_admission.py:186`, `src/cadrumo/entrypoints/runtime/profile_connection_attendance.py:101`). Attendance is refused to every non-MCP frontend (`profile_connection_attendance.py:81`), so a piped command cannot borrow the hold. The hold and the leaf logout both pass `persist_receipt=False` (`src/cadrumo/entrypoints/cli/config/sign_in_hold.py:81`, `src/cadrumo/entrypoints/cli/config/custody.py:399`). Identity is the kernel-verified connection plus an OS-owner equality check (`profile_connection_attendance.py:148`). The child is grantless; its scope is the parent intersected with the profile ceiling, and its expiry is at most the earlier of the parent's and the access-lease maximum (`src/cadrumo/application/user_profile/session_authority_admission.py:569`). It is revalidated by lineage (`session_authority_core.py:256`) and retired with its parent (`session_authority_core.py:189`).

## Findings

### attendance-peer-facts | medium | the holder sees only a pid; the image path the decision records is neither captured nor shown

`src/cadrumo/application/runtime/attendance.py:70` records process id, frontend and surface only, because `RuntimePeer` carries just the OS owner and process id (`src/cadrumo/application/runtime/contracts.py:174`). Constraint 2 of the decision commits to recording the image path as well, and constraint 3 to reporting verified peer facts; the Amendments do not reconcile this. `docs/how-to/connect-an-agent.md` mitigates it by telling the person to approve only the process id they started.

### expired-lease-refusal-shape | medium | an expired attended lease answers credential_rejected, read as tampering and not as a session end

`src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:118` raises `CREDENTIAL_REJECTED` for a lease that `expire()` has dropped. An attended lease lasts at most five minutes, so a call landing just after expiry gets that code. `src/cadrumo/adapters/local_runtime/frontend_client.py:92` maps it to a tampered refusal, and it is absent from `_SESSION_ENDED` (`src/cadrumo_harness/mcp/runtime_adapter.py:62`), so that call neither renews nor releases. The next call recovers through the retirement notice. This likely explains the single unreproduced `credential_rejected` seen after a `ledger.add` commit during S05.

### ledger-completeness | medium | four S05 paths are unlogged, one of them a packaging change outside the Step's declared scope

fa4f7dc9c5 touched `native/CONTRACT.md`, `native/package-layout.json`, `src/cadrumo/adapters/local_runtime/frontend_client.py` and `src/cadrumo_harness/mcp/runtime_adapter.py`, none of which appeared in the S05 rows. The package-layout edit admits `CADRUMO_CLI_REVEAL_IDENTIFIERS` to the installed override allowlist, so the packaged CLI can show profile ids. The operator listed the package hiding ids despite that setting as a gap to close on 2026-10-12, so the change is requested scope; it was not logged. The S05 rows were appended on 2026-10-13 with this note.

### attendance-coverage | medium | the declared attendance bounds and the person-only door have no automated test

`src/cadrumo/entrypoints/runtime/tests/test_attendance.py` covers approval and cascade, decline and holder close, and lapsed-lease reissue. Nothing exercises `ATTENDANCE_PENDING_LIMIT`, the 120-second lapse (`profile_connection_attendance.py:229`), the duplicate-ask conflict, or the non-MCP refusal at `profile_connection_attendance.py:81`, which is the gate that keeps a piped command from being attended. The packaged proof does not cover them either.

### client-identity-aliasing | low | the holder and every attended child share one client id, kept even after a denied approval

`profile_connection_attendance.py:303` gives the recipient the holder's client id, as amended, and leaves it assigned when `attend` then denies (line 310). Current authority paths also bind the connection id, and no bypass was found.

### logout-proof-order | low | logout with a secrets channel always signs in by password instead of first trying a receipt

`src/cadrumo/entrypoints/cli/config/custody.py:392` performs a password login whenever the channel is supplied, while constraint 4 applies the leaf proof only when no receipt resumes. The behaviour is stronger than the decision's wording.

### orphan-ask | low | a failed renewal can leave a pending ask occupying a slot until it lapses

When `_renew_attendance` finds no approval it has already created a fresh ask (`runtime_adapter.py:316`, `profile_connection_attendance.py:118`) that the released connection never claims. It is shown to the holder, approving it is refused at `profile_connection_attendance.py:297`, and it lapses after 120 seconds.

## Recommendations

- attendance-peer-facts: decide whether peer evidence includes the image path. Either extend `RuntimePeer` and the attendance candidate with it, or amend constraint 2 of the decision to state that peer evidence is the process id plus the enforced OS owner. A follow-on amendment must make that choice.
- expired-lease-refusal-shape: map a custody refusal for an expired lease to the session-expired reason, or add the code to `_SESSION_ENDED`, so the approved connection renews on the same call; cover it with a test that lets a lease lapse between two calls.
- ledger-completeness: done on 2026-10-13 by appending the four rows to S05 with the operator's request as the basis.
- attendance-coverage: add connections-layer tests with an injected monotonic clock for the pending cap and the lapse, a duplicate-ask test, and a test that a non-MCP frontend is refused attendance.
- client-identity-aliasing: restore the recipient's own client id when an approval is denied, and add a test asserting that no authority is keyed on client id alone.
- logout-proof-order: amend the constraint wording to the implemented behaviour, or attempt receipt resume first.
- orphan-ask: forget the ask of a connection whose renewal failed, or let renewal ask without creating a pending entry.

## Resolutions

The operator asked on 2026-10-13 for the findings to be fixed; S06 of `2026-10-12-attended-live-sign-in-plan` carries the fixes. Each one implements a constraint the decision already states, so the decision is unchanged.

- expired-lease-refusal-shape: fixed at the source. Worker custody remembers the leases its expiry dropped (`src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:181`), and a request on one is refused as `session_expired` (`profile_worker_custody.py:131`). That code is already in `_SESSION_ENDED`, so an attended connection renews on its next call. A lease that was retired, not run out, keeps `credential_rejected`. Covered by the `attended_child_lapse` case and tightened assertions in `src/cadrumo/adapters/persistence/storage/master_key/tests/test_profile_worker_custody_lease_window.py:267`. The refused call itself is not retried, because the refusal can arrive after the operation began.
- attendance-peer-facts: fixed on Windows. `RuntimePeer` carries `image_path` (`src/cadrumo/application/runtime/contracts.py:181`), read from the retained process handle (`src/cadrumo/adapters/local_runtime/windows_channel.py:69`), and it travels through the ask and the candidate to the hold command's `attendance_request` event. The how-to now tells the person to check it. Asserted against an independent read of the process image in `src/cadrumo/entrypoints/runtime/tests/test_attendance.py:162`.
- attendance-coverage: fixed. `test_asks_are_bounded_in_number_and_time_and_only_an_agent_may_ask` (`test_attendance.py:281`) covers refusal of a person's frontend, the duplicate-ask conflict, the pending cap, the lapse and the freed slot. It uses a real transport and real workers, with the cap and lapse lowered for the test.
- client-identity-aliasing: fixed. A refused or failed approval restores the recipient's own client id (`src/cadrumo/entrypoints/runtime/profile_connection_attendance.py:311`). No test reaches an authority denial at that point.
- logout-proof-order: fixed in code to match constraint 4. Logout with a secrets channel first tries the stored sign-in and uses the password only when none resumes (`src/cadrumo/entrypoints/cli/config/custody.py:402`). Covered by `test_logout_proves_the_person_by_a_stored_sign_in_before_the_password`.
- orphan-ask: fixed. A connection whose approval ended is marked spent (`profile_connection_attendance.py:222`, `:354`) and makes no new ask (`:100`); it must reconnect to ask again, which is what the MCP harness does. Covered in `test_a_declined_ask_admits_nothing_and_closing_the_holder_ends_attendance`.

### attendance-peer-facts-posix | low | Linux and macOS still report no image path

The POSIX transport reads only the uid and pid (`src/cadrumo/adapters/local_runtime/posix_channel.py:83`), so `image_path` is `null` there. On macOS the audit-token path read deliberately never discloses the path (`src/cadrumo/adapters/local_runtime/macos_login.py:87`). Linux has no retained process handle, so a path read from the pid could race pid reuse. Closing this needs either a pidfd-anchored Linux read and a macOS audit-token read, or an amendment to constraint 2 that limits the image path to Windows.

## S06 re-review

On 2026-10-13 an independent read-only reviewer re-reviewed commit f0b54b5717 (S06). Verdict: pass with findings. Nothing was critical or high, and the four operator constraints held. The new custody refusal is caught at every worker and runtime boundary. `_attendance_spent` is bounded by live connections.

### peer-identity-widening | medium | adding image_path made the program path part of peer equality

`RuntimePeer` compared every field, so every `context.peer != channel.peer` gate, and the two cross-channel worker checks, required two separate path reads to agree. A link replaced between the reads would refuse a healthy worker.

### logout-receipt-first-unmapped-refusal | medium | an unmapped receipt refusal skipped the password fallback

`resume_receipt` re-raises a `RuntimeFrontendRefusedError` for any denial outside `_RUNTIME_RECEIPT_REFUSALS`. Logout fell back only on `ProfileReceiptRefusedError`, so it failed even though a valid password was supplied.

### worker-exit-refusal-tuple | low | the worker's refusal exit did not name the new error type

### attendance-spent-on-transient-denial | low | any attend denial spent the connection, not only an ended sign-in

### client-id-restore-window | low | the client id was swapped and restored outside the connections guard

### logout-evidence-is-a-stub | low | the logout ordering test drives a hand-written client

## S07 resolutions

S07 fixes the re-review findings and closes `attendance-peer-facts-posix`, under the operator's 2026-10-13 instruction to keep working the findings.

- peer-identity-widening: fixed. Peer equality and hashing compare only the OS owner and the process id (`src/cadrumo/application/runtime/contracts.py:185`). Covered by `src/cadrumo/application/runtime/tests/test_runtime_peer.py`.
- logout-receipt-first-unmapped-refusal: fixed. Logout tries `resume_receipt` explicitly and falls back to the password on any refusal of it (`src/cadrumo/entrypoints/cli/config/custody.py:404`). The test adds an unmapped-refusal case.
- worker-exit-refusal-tuple: fixed (`src/cadrumo/entrypoints/runtime/worker.py:285`).
- attendance-spent-on-transient-denial: fixed. A denied renewal asks the authority whether the person's session still lives (`src/cadrumo/entrypoints/runtime/profile_connection_attendance.py:222`). Only an ended session spends the connection; otherwise the approval stands and the denial is returned. No test reaches a passing denial.
- client-id-restore-window: fixed. The swap and the restore both run under the connections guard (`profile_connection_attendance.py:321`).
- logout-evidence-is-a-stub: the real-client path is the packaged proof's `logout_password_proven` step, rerun on the rebuilt bundle. No unit case was added.
- attendance-peer-facts-posix: fixed.
  - Linux reads `/proc/<pid>/exe` only while the peer's pidfd shows that exact process alive (`src/cadrumo/adapters/local_runtime/posix_channel.py:77`). A kernel without peer pidfds reports none.
  - macOS returns the path that the version-checked `proc_pidpath_audittoken` query already answered (`src/cadrumo/adapters/local_runtime/macos_login.py:81`).
  - The Linux path is proven in WSL on kernel 6.18 by `test_the_peer_program_is_read_while_its_pidfd_pins_it`. The macOS path is proven only against the faked native call; the native macOS lane runs on the macOS host.
