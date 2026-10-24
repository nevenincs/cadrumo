---
tags:
  - '#plan'
  - '#desktop-native-sign-in'
date: '2026-10-24'
tier: L1
related:
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
modified: '2026-10-24'
body_schema: body-v2
body_hash: 'sha256:60d927731ccd0867e8500b57cf1948cdf73dde201557ec575426fe99e112380a'
---

# `desktop-native-sign-in` plan

The desktop window holds the person's runtime session on its own native connection; the Python hold child leaves the desktop.

## Description

Approved 2026-10-24. Basis: the user's instruction of 2026-10-24, "Your only task is implementing candidate 1: native sign-in", which named retiring the desktop's Python `session hold` child and the remaining sign-in children.

Decision coverage: the 2026-10-24 amendments of `2026-10-04-application-sign-in-adr` and `2026-10-04-desktop-shell-adr` record the ownership change (the window holds its own person session; the hold command stays for development probes and attended admission). Non-Windows sign-in stays unavailable, as those records already rule, because no login and lock observer exists there; the native transport stays Windows-only.

Today the window already signs in natively (`native/desktop/src-tauri/src/shell/sign_in/mod.rs`, `native_sign_in`), but every person request (status, activity, service admission, attendance, language, presentation and the registered-operation relay) still crosses a Python child (`native/desktop/src-tauri/src/agent/person.rs`, `src/cadrumo_runtime/host/session_hold.py`). The work moves those requests onto the window's connection in Rust, keeps the hold's reply shapes so the agent host, language, ledger, presentation and relay consumers stay unchanged, and resumes a stored sign-in natively where the window holds none.

## Steps

- [x] `S01` - keep refusal detail and session-scoped events in the native runtime client, add a session-exchange seam and the receipt resume with its retry and refusal map; `native/application/src/runtime_client.rs`.
- [x] `S02` - port the hold's registered-operation relay and profile language read and set to Rust over that seam, with fake-exchange unit tests; `native/application/src/person_operations.rs`.
- [x] `S03` - hold the window's person session on its own native connection with the hold's reply shapes, retire the hold child and prepared hold from sign-in, and move consumer tests to the native session; `native/desktop/src-tauri/src/agent/person.rs, native/desktop/src-tauri/src/shell/sign_in/mod.rs`.
- [x] `S04` - extend the live native client proof to the person session and time native sign-in against a real runtime; `native/application/src/runtime_client.rs, dev/runtime_lifecycle/native_client_live.py`.

## Parallelization

S01 lands first: it defines the session-exchange seam. S02 and S03 then run in parallel with disjoint files: S02 owns `native/application/src/person_operations.rs` and its registration in `native/application/src/lib.rs`; S03 owns `native/desktop/src-tauri/src/agent/person.rs`, `native/desktop/src-tauri/src/shell/sign_in/` and their tests, and wires S02's API once it lands. S04 follows both.

## Verification

- `cargo test` passes for `native/application` (with the `platform` feature) and `native/desktop/src-tauri`, including the person-session and operation-relay unit tests; clippy and rustfmt are clean.
- The desktop crate spawns no `session hold` child: no `"session", "hold"` argument remains under `native/desktop/src-tauri/src`.
- The live proof (`dev/runtime_lifecycle/native_client_live.py`) signs in, holds, reads status, notes activity, reads the profile language through the relay and signs out against a real runtime, and reports the native sign-in time.
- One integrated review at plan close.
