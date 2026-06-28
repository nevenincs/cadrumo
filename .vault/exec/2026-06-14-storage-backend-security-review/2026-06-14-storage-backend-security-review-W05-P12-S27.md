---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S27'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Delete the v1 portable-bundle compat branch and drop version 1 from the supported set per no-legacy-compatibility

## Scope

- `src/aeat/application/user_profile/_bundle.py`

## Description

- Drop `1` from `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` (now `{2}`), delete the
  now-unreachable `if bundle_schema_version == 1` facts-only branch in
  `deserialize_profile_bundle`, and rewrite the v1-rationale docstrings/comments
  in `_bundle.py` and `_portable_export.py` to the v2-only reality.

## Outcome

The v1 portable-bundle compat path is deleted, not bridged, per the ADR
adjudication that `no-legacy-compatibility` supersedes the 2026-05-27 portability
ADR's v1-importable clause (pre-beta, no released bundles, no writer emits v1). A
v1 bundle is refused by the supported-version gate. 24 bundle/lifecycle/export
tests green. Committed in `fbffabc98`.

## Notes

The empty-tuple field defaults remain — they model a category with no rows, not
v1 compatibility.
