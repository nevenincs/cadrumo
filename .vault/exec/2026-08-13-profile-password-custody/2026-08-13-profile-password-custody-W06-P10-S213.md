---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d171031548d5b3b0ee0f91ce1f09be03db286f0b7bba2ac7316022270c1a403f'
step_id: 'S213'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Require register_profile_with_credentials to receive a recovery handoff and publish a profile only after exact possession verification succeeds, with refusal or cancellation leaving no profile behind

## Scope

- `src/cadrumo/application/user_profile/_registration.py and src/cadrumo/application/user_profile/_custody_service.py`

## Description

- Require every `register_profile_with_credentials` call to provide a recovery handoff that returns the operator's possession proof.
- Compare the returned proof against the one-time mnemonic inside the application boundary before entering capsule publication.
- Refuse enrollment publication at the custody transaction owner when no recovery envelope is present.
- Exercise the real registration and custody writers for successful enrollment, missing handoff, inexact proof, callback refusal, key wiping, and password-only publication refusal.

## Outcome

New profiles cannot be published by the application registration door without a recovery wrapper whose exact phrase possession was proved before publication. A missing handoff is rejected by the required call contract, an inexact proof raises `ProfileRegistrationError`, callback cancellation or failure propagates, and each refusal leaves no committed profile. The deeper custody writer independently refuses an enrollment publication without a recovery envelope. Password login and restore authority were not changed.

Verification completed with the combined eighteen-test registration and lifecycle suite, scoped Ruff and type checks, a clean scoped diff check, and an independent safety review with no remaining CRITICAL, HIGH, or MEDIUM findings.

## Notes

The required callback return type intentionally makes older direct creation callers invalid until the immediately following consumer-migration Steps update them. No compatibility default or password-only fallback remains at the application boundary. The focused type check initially exposed an existing `Mapping`-versus-`dict` mismatch on the touched registration refusal path; normalising that context removed the diagnostic without changing its payload.
