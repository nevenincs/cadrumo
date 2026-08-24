---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7ab4ec1b2f4ce20ed1368be644b833a0555844b56811b70c82ac766ebe683ee1'
step_id: 'S184'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether the profile subject of the bucket history verb was meant to become optional, since the live command now yields an empty required-input set while the profile parameter is still declared, so a schema test asserting the subject is required fails on a key error and nothing swept it when the change landed, and a single-subject verb losing its required subject is either a deliberate widening nobody recorded or an accidental one that changes what the operator must supply

## Scope

- `src/cadrumo/entrypoints/cli/_config/ and src/cadrumo/entrypoints/cli/tests/test_verb_input_schema.py`

## Description

Adjudicate the bucket-history subject widening against the shipped command metadata and update the schema proof to assert the optional live parameter contract.

## Outcome

Ruled: the bucket-history subject widening was deliberate (part of the d18e37c274 verb rework to bucket-scoped reads with an active-profile fallback; the operator help already documents `[PROFILE]`). The schema test now reads `profile` from the live parameter metadata, asserts `required is False` and `required_inputs == ()`.

## Notes

The contemporaneous execution record reported no additional incident beyond the ruling and implementation evidence retained above.
