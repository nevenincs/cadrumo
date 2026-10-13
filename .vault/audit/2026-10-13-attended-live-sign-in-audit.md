---
tags:
  - '#audit'
  - '#attended-live-sign-in'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:14634428f707d8a81ca7b2b0d904f0e1c03632510d683847235459b71aabdf96'
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
