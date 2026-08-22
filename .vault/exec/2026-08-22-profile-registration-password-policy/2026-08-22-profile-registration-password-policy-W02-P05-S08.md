---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:98f520f859c5ec70c5ef8687651699326b8de808c9f05923926f4f472d774ad2'
step_id: 'S08'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---




# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then collapse malformed and incorrect existing-password proofs without hiding operational faults and prove login restore and recovery authorization behavior

## Scope

- `src/cadrumo/application/user_profile`

## Description

- Ground every existing-password proof capability and the custody error taxonomy through semantic and exact discovery.
- Introduce one authentication-specific application refusal with a stable translation key and no context, measurements, or submitted secret.
- Require an explicit proof operation when mapping custody password failures and delete the broad predicate and all consumers.
- Map login, password restore, recovery-artifact export, and password-rotation authorization while preserving login throttle behavior.
- Preserve record, integrity, transaction, resource, supervision, archive, and unavailable-storage failures unchanged.
- Update the minimal error-registry declaration and CLI login consumer atomically without touching locale files.

## Outcome

Malformed and cryptographically incorrect existing profile passwords now produce the same `ProfileAuthenticationRefusedError`, translation key, and empty context for login, password restore, and recovery export. Login records the same throttle failure before raising the public refusal. Current-password rotation retains its operation-specific outer error while using the same non-oracular proof classification internally. No recovery-password reset or recovery-secret behavior changed; no recovery-removal capability exists in the live application surface.

Focused Ruff and format checks pass. The targeted non-oracular, mutation-safety, operational-distinction, throttle, and recovery tests pass 7 cases. The complete recovery and rotation lanes pass 39 cases, and 87 focused application cases collect. The full login-handover lane passes 22 of 29 cases; seven pre-existing Windows keyring acceleration/crash-resume cases fail because the test backend reports `KeyringUnavailableError`, independently of password-proof mapping.

## Notes

The new exception required one atomic core error-registry declaration because undeclared `CadrumoError` subclasses are rejected at import time. Deleting the obsolete predicate also required one minimal CLI login consumer update to preserve absent-channel guidance without a runtime import failure. Both dependencies were explicitly authorized for S08; locale population remains S10-owned.
