---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:a8bd9979be69291b93f0de77a5d58edb19b3783bc78d0a8daf0981f2c06dfb4b'
step_id: 'S184'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether the profile subject of the bucket history verb was meant to become optional, since the live command now yields an empty required-input set while the profile parameter is still declared, so a schema test asserting the subject is required fails on a key error and nothing swept it when the change landed, and a single-subject verb losing its required subject is either a deliberate widening nobody recorded or an accidental one that changes what the operator must supply

## Scope

- `src/cadrumo/entrypoints/cli/_config/ and src/cadrumo/entrypoints/cli/tests/test_verb_input_schema.py`

## Description

## Outcome

Ruled: the bucket-history subject widening was deliberate (part of the d18e37c274 verb rework to bucket-scoped reads with an active-profile fallback; the operator help already documents `[PROFILE]`). The schema test now reads `profile` from the live parameter metadata, asserts `required is False` and `required_inputs == ()`.

## Notes
