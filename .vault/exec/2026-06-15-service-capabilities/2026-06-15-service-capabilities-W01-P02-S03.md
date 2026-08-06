---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-07-17'
body_hash: 'sha256:af9577f1d8dc57bbaf1f13990b93a25b2da131562069d2c33085ea633c768254'
step_id: 'S03'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

# Add resolve_capability + CapabilityDecision overlaying profile facts onto the global Settings default (gestor-mode absolute bar first)

## Scope

- `src/aeat/application/user_profile`

## Description

- Add `resolve_capability` + `resolve_active_capability` + `CapabilityDecision`/`CapabilitySource` overlaying the profile fact onto the global Settings default; gestor-mode is the absolute first bar for cloud upload.

## Outcome

The resolver is the single posture computation; 4 tests cover default/profile/gestor/global-flag.

## Notes

Capabilities narrow, never widen, the safety floor (service-capabilities ADR).
