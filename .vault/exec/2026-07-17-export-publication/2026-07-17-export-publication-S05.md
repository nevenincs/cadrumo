---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:dd3a08ccc0f051d56dcc2d34db2f7331aba08a4775c789dcc80ca29dbf0df21c'
step_id: 'S05'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Prove portable-transfer and subject-access purposes use the same service and bundle schema, derive categories from serialized fields and registry-carried namespaces, and retain distinct purpose metadata

## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export.py`

## Description

- Add `test_bundle_export.py` proving both purposes resolve through one `export_profile_bundle` service and one bundle schema against real secure storage.
- Prove data categories derive from the serialized bundle fields and, via a pure-logic case over a real coverage manifest, from carried registry namespaces.
- Prove distinct purpose metadata survives the shared service (two `PROFILE_EXPORTED` events with distinct purposes, identical categories and schema).
- Retain the encrypted-transport roundtrip and the real-trigger event-failure compensation proofs from the superseded authority test.

## Outcome

Six real-behavior cases pass with real profile creation, real secure SQL storage, and a real SQLite constraint trigger for the compensation case. No mocks, stubs, or tautologies. Committed in `ac097a53a7`.

## Notes

Supersedes and removes the prior `test_bundle_export_authority.py`; all its real assertions were folded in, so no coverage was lost.
