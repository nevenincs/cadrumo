---
name: cadrumo-alta-contribuyente
description: >-
  Set up a new taxpayer in Cadrumo: confirm the signed-in profile exists, record
  the taxpayer's identity (NIF/CIF/DNI/NIE/NII) and circumstances on it, check
  read-only AEAT access (the person configures it) and confirm the workspace is
  ready. Use when starting with a new taxpayer, before any ledger or modelo work.
applies_when:
  workflow_phase: onboarding
---

# Onboard a taxpayer

The profile is the unit of isolation: you work inside the one profile the person
is signed in to. Record who the taxpayer is, confirm readiness, and state what is
still missing. No tax value is computed here.

## Procedure

1. Call `status`. If the session is `none` or no profile exists yet, creating a
   profile sets its password, which is the person's own act: ask them to create it
   in Cadrumo (`aeat config profile create <name>`) or to sign in, and continue
   once they have. Never ask for or repeat the password.
2. Record only the identity and circumstances the person has told you. Say which
   facts you are about to write, then run `aeat config profile edit --quiet` with
   just those flags (for example `--tax-id`, `--name`, `--surnames`,
   `--entity-type`, `--fiscal-residency`; `aeat config profile edit --help` lists
   them all). Do not add `--accept-defaults`: it fills every flag you did not give
   with a default, and those are not facts the person stated. Tool server: the
   operation `user-profile.patch` (find it with `search`, read its schema with
   `describe`).
3. Read the profile back with `aeat config profile view` (operation
   `user-profile.view`) and check the identity and circumstances against what the
   person said. `aeat config profile status` reports readiness and what the profile
   still lacks and the next authorized action; ask the person for the missing
   facts and record them as in step 2.
4. If the work needs live AEAT reads, check access with
   `aeat config auth status` and `aeat config auth test` (both read local state
   only). The person configures the AEAT provider, certificate, key or grant and
   enters any secret in Cadrumo, never in the conversation. State what is missing
   and wait.
5. Confirm the workspace with `aeat app overview status` (operation
   `overview.status`): read that it reports the profile and an empty work state.

## Success assertions

- `aeat config profile view` shows the identity the person gave, and nothing the
  person did not give.
- `aeat app overview status` reports the profile.
- No secret appears anywhere in the conversation.

## Next

With the profile ready, load `cadrumo-llevar-libro` to build the ledger. For a
taxpayer starting an economic activity, load `cadrumo-inicio-actividad` first.
