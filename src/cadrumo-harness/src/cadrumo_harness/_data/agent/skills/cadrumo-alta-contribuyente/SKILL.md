---
name: cadrumo-alta-contribuyente
description: >-
  Onboard a new taxpayer: create the profile, capture identity (NIF/CIF/DNI/NIE/
  NII), establish read-only AEAT access, and confirm the workspace is ready. Use
  at the start of a new engagement before any ledger or modelo work.
applies_when:
  workflow_phase: onboarding
---

# Onboard a taxpayer

The profile/bucket is the unit of isolation. Create it, identify the taxpayer, and
confirm readiness. No tax value is computed here.

## Procedure

1. Create the profile: `aeat config profile create` with the taxpayer's label and
   identity. Read the envelope; note the profile is now the active context.
2. Confirm it: `aeat config profile view` - verify the identity (NIF/CIF/DNI/NIE/
   NII) and circumstances are recorded correctly.
3. Establish read-only AEAT access if the engagement needs live reads:
   `aeat config auth configure`, then `aeat config auth status` and
   `aeat config auth test` to confirm.
4. Confirm readiness: `aeat app overview status` reports the active profile and an
   empty work state.

## Success assertions

- `aeat config profile view` returns `status` success with the taxpayer's identity
  present.
- `aeat app overview status` reports the profile as active.
- No secret material appears in any narration; custody stays in the bucket.

## Hand off

The workspace is ready for the bookkeeper (`cadrumo-llevar-libro`) to build the ledger.
