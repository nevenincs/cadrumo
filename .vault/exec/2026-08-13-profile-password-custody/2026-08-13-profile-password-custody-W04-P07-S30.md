---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:9964a8c1447529c93bbdd190e7207788f5f44833de3866d5e1125e09ba9b88cd'
step_id: 'S30'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh collapse the forwarding profile-custody port into one canonical route to the session and custody surface, making that route exclusive so no application module reaches the adapter package by a second path, and removing the mirror protocols and delegate wrappers that duplicate names already owned elsewhere

## Scope

- `src/cadrumo/application/profile_custody/ and src/cadrumo/application/`

## Description

Dissolve the forwarding custody port into the user-profile owner, repoint every consumer and dynamic reach, delete the retired package, and re-run the hard-cutover absence gate.

## Outcome

The forwarding port is dissolved in one atomic relocation (commit `3f1a947674`): all seventy-five names the port exported now live in `application/user_profile/_custody_ports.py` (protocols, the local-record delegates and factories, the pure helpers, the composition ops and the session forwards), promoted through the user-profile facade `_LAZY_EXPORTS`. The five dynamic `import_module("cadrumo.adapters.persistence.storage.custody")` reaches became static facade imports; the thirty-three consumer files repoint at the facade; the port package, its tests and its API stub are deleted; the hard-cutover absence gate's declared open violation moved from `profile_custody/__init__.py` to `user_profile/_custody_ports.py` (one static master-key import, reason text updated) and the gate passes 12/12. The error registry binds `ProfileRecordCryptoError` under its new module path.

Two executor runs died mid-step (prompt overflow) after converting the dynamic imports and moving the first helper tranche; the sweep, facade promotion and deletion were completed by the lead session.

## Notes

Gates: ruff clean on the touched set; collect-only on `src/cadrumo/application/` clean (8703 collected, 0 errors); affected suites green except two pre-existing classes: the concurrent authority-grade registry sweep's tree-wide `RegistryValidationError` red (S195's documented external blocker), and the UUID-harness fixture errors from commit `58cd742301` (readable bucket ids through `UUID(str(profile_id))` in `profile_capsule.py:300`) — routed to S106. `_custody_ports.py` was rebuilt by concatenation and re-linted; facade duplicate keys deduplicated against the pre-existing entries (`export_profile_recovery_artifact` stays on `._recovery_custody`).
