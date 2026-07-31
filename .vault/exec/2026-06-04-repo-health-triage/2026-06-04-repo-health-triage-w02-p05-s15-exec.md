---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:cfe79e3f1e80e1cc94b72582334028e0c94fc0c191fa8facf51158a9510b2e4b'
step_id: 'S15'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W02.P05.S15`

Scope: `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.

## Description

- Added `SecureBoundRepository.payload_model()` as the typed payload accessor.
- Preserved the legacy `payload_type` fallback for repositories outside this
  W02 slice.
- Switched envelope construction to the accessor.

## Outcome

Scoped subclasses can avoid invariant `ClassVar` payload overrides without
changing secure envelope load, save, or iteration behavior.

## Notes

The fallback keeps non-W02 repositories compatible until they are migrated in
later slices.
