---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:916520206f3d5d3ab6260720208a3d922ba86d1106b276d8cd371d2aff056b30'
step_id: 'S01'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Define typed portable-transfer and subject-access export purposes, requests, results, target identity, and categories derived from the actual portable bundle schema and carried registered namespaces while keeping sealed recovery archives separate

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_contracts.py`

## Description

- Create `_bundle_export_contracts.py` owning the closed value sets and typed envelopes for the sole export service.
- Declare `ProfileBundleExportPurpose` (portable transfer, subject access) and `ProfileBundleExportTransport` (cleartext-local, passphrase-encrypted) as core-style StrEnums.
- Move `ProfileBundleExportRequest` and `ProfileBundleExportResult` out of the service module into the contract surface.
- Add a `ProfileBundleExportTarget` model whose computed `identity` resolves the destination to a canonical absolute path for same-target locking and operation-state keying.
- Add `bundle_data_categories`, deriving categories from the serialized `UserProfilePortableExport` field names and the coverage manifest's carried registry namespaces, never a static list.
- Keep the sealed recovery archive out of this surface entirely.

## Outcome

Contracts module compiles and lints clean. `export_profile_bundle` and both purposes now share one typed contract source; category derivation traces to real schema fields plus carried namespaces. Committed in `a9251f5fa2` with steps S02-S04.

## Notes

Sealed recovery archive semantics deliberately excluded per the ADR; this surface is portable-export only.
