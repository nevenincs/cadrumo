---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:bb82841ee19348dd17bd124e8eebb7aab1e33e58db5668e437e60230f298b86d'
step_id: 'S08'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Build the coverage manifest and apply the fail-closed full-coverage assertion for the sealed profile

## Scope

- `src/aeat/application/user_profile/_bundle.py`

## Description

- Build `CoverageManifest` from populated secure-object namespaces and row counts.
- Mark typed bundle namespaces as covered by the typed payload fields.
- Fail closed when the full custody profile sees a populated namespace outside the covered set.
- Update the cleartext CLI roundtrip assertion to expect populated row counts and explicit exclusions.

## Outcome

- Complete. Full custody fails closed for uncovered populated namespaces; structured cleartext export records that it is partial.
- Verified by `test_custody_completeness.py`, `test_profile_export_roundtrip.py`, and reviewer pass.

## Notes

- The old empty-manifest assertion was stale after the coverage implementation and was replaced with the concrete structured manifest observed through the real CLI path.
