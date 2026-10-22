---
tags:
  - '#plan'
  - '#startup-performance'
date: '2026-10-22'
tier: L1
related:
  - '[[2026-10-22-startup-performance-authority-observation-adr]]'
  - '[[2026-10-22-startup-performance-request-path-audit]]'
modified: '2026-10-22'
body_schema: body-v2
body_hash: 'sha256:4d5388b4537c92ff5690bfb95472a34df33347cbaf4ecead0c3bbb3e66e67074'
---

# `startup-performance` plan

Make sign-in to a usable first screen fast by removing the request-path costs measured in the request-path audit.

## Description

Approved 2026-10-22. Basis: the operator's instruction in this session, "fix the roots causes. if you have to refactor everything", given with a measured 40-50 s launch against an expected sub-2 s one. The operator did not answer the follow-up question offering the three design options within five minutes; the recommended options are taken under that instruction and remain open to the operator's veto.

The findings are in `2026-10-22-startup-performance-request-path-audit`. `2026-10-22-startup-performance-authority-observation-adr` governs S02-S04. S06 and S07 each change a settled design (a pre-started worker; the desktop sign-in process chain, which amends the desktop shell's sign-in observation) and get their own ADR before they execute. S01, S05, S08, S09 and S10 are implementation within existing decisions: `2026-10-13-startup-performance-operation-contract-manifest-adr`, `2026-10-16-idle-churn-adr` and `2026-10-17-idle-churn-operation-observation-adr` are unchanged. The staged package is the operator's running application; it is rebuilt only with the operator (S10). Measurements in between use an independent copy with changed modules overlaid.

## Steps

- [x] `S01` - Memoize the redaction gate's NIF-IVA catalogue and Spanish format per authority incarnation and Madrid date so log scrubbing stops re-resolving registry facts per record; `src/cadrumo/domain/calculations/registry/tax_identity_admission.py and its tests`.
- [x] `S02` - Add the custody change witness over directory change notifications with re-arm-before-read, unwatchable fallback and 0.5 s maximum age; `src/cadrumo/adapters/persistence/storage/custody/change_witness.py and its tests`.
- [x] `S03` - Serve runtime facts lock, enrollment and binding observations and the logon inventory through the witness and WTS invalidation, invalidating on own publications; `src/cadrumo_runtime/host/profile_host.py, src/cadrumo_runtime/host/profile_connections.py, custody stores and owning tests`.
- [ ] `S04` - Serve the worker's capsule binding validation through the witness; `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py and owning tests`.
- [ ] `S05` - Measure the request path on an overlaid package copy and record before and after timings in the audit; `.vault/audit/2026-10-22-startup-performance-request-path-audit.md`.
- [ ] `S06` - Pre-start one unbound profile worker so sign-in binds an imported worker and the first operation skips cold start; `src/cadrumo_runtime/adapters/profile_worker*.py, src/cadrumo_runtime/host/worker*.py and owning tests`.
- [ ] `S07` - Remove CLI children from the desktop sign-in path: profile inventory from session watch, password sign-in through a pre-started session hold that persists the receipt; `src/cadrumo_runtime/host/session_watch.py, session_hold.py, native/desktop/src-tauri/src/shell/sign_in and owning tests`.
- [ ] `S08` - Stop hashing the whole authority database in every process while keeping corruption refusal; `src/cadrumo/domain/calculations/registry/authority_store.py and owning tests`.
- [ ] `S09` - Cut the TUI first screen's serial operations and eager imports; `src/cadrumo/entrypoints/tui and src/cadrumo_client/transport/frontend_profile_view_client.py`.
- [ ] `S10` - Rebuild the stage with the operator, measure the real desktop launch to usable Home and confirm no slow-request warnings; `build/windows-x64/stage/Release/app, audit`.

## Parallelization

Sequential by default: S02 precedes S03 and S04, and S05 measures S01-S04. S07's desktop half and S08 touch disjoint files from S02-S04 and may run in parallel with them once their ADR is accepted. One owner commits and logs.

## Verification

- Each Step's owning tests pass, including a test that fails against the previous code for each behaviour change: an out-of-process custody publication invalidates the observation before the next check, an unwatchable directory reads per check, a raising read is not cached, and a memoized gate answers like the unmemoized one.
- Ruff, format, `just check-types`, import contracts and `dev/quality/tests/test_no_git_cli.py` pass on touched files.
- The disposable-root harness shows, against the same package copy, a `user-profile.view` page and the login and hold admissions faster than the audit's baseline, with the numbers recorded in the audit.
- S10: on the rebuilt stage, the operator's launch reaches Home with no `session_hold_request_slow` warning.
