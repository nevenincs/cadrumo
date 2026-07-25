---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S84'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Define typed portable-transfer and subject-access export purposes, requests, results, target identity, and categories derived from the actual portable bundle schema and carried registered namespaces while keeping sealed recovery archives separate

## Scope

- `src/cadrumo/application/user_profile/_commands.py`
- `src/cadrumo/application/user_profile/_bundle.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD rather than a fresh edit. The predecessor profile-export-consolidation campaign landed the typed contracts in commit `a9251f5fa2`, hardened by `ac097a53a7`, `c2fb2a71da`, and `b1058ef9f7`.

- Declare `ProfileBundleExportPurpose` (`PORTABLE_TRANSFER` / `SUBJECT_ACCESS`) and `ProfileBundleExportTransport` (`CLEARTEXT_LOCAL` / `PASSPHRASE_ENCRYPTED`) as closed `StrEnum` value sets.
- Declare `ProfileBundleExportRequest` (typed input: profile name, destination, purpose, transport, optional passphrase) and `ProfileBundleExportResult` (published identity plus disclosed and excluded data categories).
- Declare `ProfileBundleExportTarget`, whose computed `identity` property canonicalises the resolved destination path so same-target locking and operation-state journal keying are deterministic regardless of the literal spelling an operator supplied.
- Derive `bundle_data_categories` from the actual serialized field names on the real portable bundle schema plus the registry namespaces the bundle's coverage manifest reports carried, rather than a static hand-maintained list.
- Derive `bundle_excluded_data_categories` from the same coverage manifest's excluded namespaces, so a subject-access response can state what it omits alongside what it carries.
- Add `_refuse_unclassified_bundle_fields`, which hard-refuses when a bundle schema field has no declared personal-data classification, so an unmapped future field cannot silently drop out of the disclosed category set.
- Keep the sealed recovery archive (`write_sealed_archive` / raw `serialize_profile_bundle` composition in `bucket_maintenance/_service.py`) a deliberately separate format with its own confidentiality and restoration semantics, not folded into this typed export surface.

## Outcome

Both operator purposes share one typed request/result/target shape and one schema-derived category-classification mechanism; a future portable-bundle field is either mapped to a category, declared envelope metadata, or declared carried-namespace derived, or the classification refuses loudly rather than silently narrowing the disclosed set.

Verified against HEAD by reading `src/cadrumo/application/user_profile/_bundle_export_contracts.py` in full and confirming the CLI consumers (`entrypoints/cli/_config/_profile_bundle.py`) import these types rather than redeclaring them. Gate: `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_bundle_export.py src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py -m "" -q` reports 29 passed.

## Notes

The originating Step row names `src/cadrumo/application/user_profile/_commands.py` and `src/cadrumo/application/user_profile/_bundle.py` as the scoped files. Neither is the canonical home of this typed contract: `_bundle.py` still owns the raw `UserProfilePortableExport` schema and `serialize_profile_bundle`/`deserialize_profile_bundle`, and `_commands.py` owns unrelated profile lifecycle commands. The purposes, requests, results, target identity, and category derivation this Step describes actually live in `src/cadrumo/application/user_profile/_bundle_export_contracts.py`, a module the predecessor campaign introduced after this plan row was authored. This is a genuine file-location divergence between the plan text and the landed implementation, not an oversight in this record.
