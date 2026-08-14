---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:5ace5412ac4190cafb9868006f0a0331dcb96f412986c0222759022c7c8711e2'
step_id: 'S85'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Move profile output-language integration tests to their application owner

## Scope

- `src/cadrumo/tests/test_output_language.py`
- `src/cadrumo/application/user_profile/tests`

## Description

- Move profile-language resolver behavior from the central harness to its application
  owner.
- Bind the tests to the real credential-first capsule registration and login lifecycle.
- Remove the fixed test credential and its security suppression.

## Outcome

The four resolver behaviors now exist only under application user-profile tests with
`unit` and `hex_application` markers. Each test isolates real profile storage, registers
a credential-protected profile, logs in through the public callback route, updates or
reads the real workflow repository, and invokes the production language resolver. All
four tests passed. The central module is deleted, and independent review found no issue.

## Notes

An earlier attempt was blocked while the shared capsule lifecycle was incomplete. After
the peer lifecycle work landed, no production fix or compatibility bridge was needed.
The final test path contains no fixed-secret suppression, private mutation, doubles,
patches, skip, or xfail. Semantic RAG remained unavailable, so exact source discovery
supplied the fallback evidence.
