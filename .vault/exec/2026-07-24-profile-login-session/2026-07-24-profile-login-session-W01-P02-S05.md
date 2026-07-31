---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:95bb86946962328ce9395ce6c81ae18132c53f0ddaf713e149bd5e3218f533b8'
step_id: 'S05'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Implement the session store (atomic secure write of session.v1 into the separated bucket keystore directory, delete, and a fail-closed resume evaluation that deletes and refuses on expiry, version mismatch, tamper, or an orphaned keychain entry), verified by targeted tests covering each refusal branch with the refusal reason asserted structurally

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py`

## Description

- Implement the session store: `profile_session_path` (keystore-separation validated), `write_profile_session` (atomic secure write of `session.v1.json`, bucket-mismatch refused), `delete_profile_session` (both artefacts, idempotent), `mint_profile_session` (session-key mint + keychain store + record write, key buffer zeroised).
- Implement `resume_profile_session`: fail-closed evaluation returning a typed `ProfileSessionResumeOutcome` plus the DEK as a separate value; refusal branches (absent, malformed, schema mismatch, foreign-bucket record, absolute then idle expiry, orphaned keychain entry, AEAD tamper) delete stale artefacts before refusing.
- Register `session.v1.json` as the `profile_session` `StoragePathDefinition` in the storage namespace registry.

## Outcome

Landed in commit `6a0fe2224e`. `TestResumeRefusalBranches` asserts every refusal reason structurally (enum member identity) and proves artefact deletion per branch; namespace-registry gate green.

## Notes

The DEK deliberately travels beside the outcome model, never on it, so no pydantic dump can surface key material. Two bucket keystore-path deferral edges (this module and the `S07` throttle sibling, which was already red at HEAD) were classified into the lazy-import allowlist with ceilings raised in the same commit.
