---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:51301689016e4ba7f5506f0fcae1c8bc2a9036eddfcd1803248afffc48af11b3'
step_id: 'S201'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether a refusal message may be keyed on a field inside one exception class, since the four distinct profile-custody refusal reasons all resolve to a single shared sentence because the error registry keys by exception class alone, so the specific cause and its recovery guidance reach the operator only as structured context and never as differentiated prose, and no existing registry entry keys on an inner field so this is a design question rather than a missing catalogue value

## Scope

- `src/cadrumo/core/errors/registry/ and src/cadrumo/adapters/persistence/storage/custody/_errors.py`

## Description

Retain class-level fallback registry binding, add instance-specific translated messages to the custody refusal, and assign reason-specific four-locale keys at all three live raise sites.

## Outcome

Ruled AGAINST field-aware registry keying: the registry binds by exception class at class-creation, and the instance `translated_message` channel is the existing per-instance differentiation (resolution precedence: instance translated_message → args[0] → class message_key). `ProfileCustodyRefusedError` now accepts `translated_message` and the three live raise sites carry reason-specific keys (`errors.refused.refused_profile_custody_legacy`, `..._kdf_resource_limit`, `..._kdf_supervision_unavailable`), authored in all four catalogues via the locales CLI. The class registry row stays as fallback.

## Notes

The contemporaneous execution record reported no additional incident beyond the ruling and implementation evidence retained above.
