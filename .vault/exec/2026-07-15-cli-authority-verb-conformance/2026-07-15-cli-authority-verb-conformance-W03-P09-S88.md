---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:60cf451dacc917081962559e165a2147dd25939b97c2a924db24449d9d43b4fe'
step_id: 'S88'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove portable-transfer and subject-access purposes use the same service and bundle schema, derive categories from serialized fields and registry-carried namespaces, and retain distinct purpose metadata

## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD rather than a fresh edit. The predecessor profile-export-consolidation campaign landed the eleven real-behaviour tests in commit `ac097a53a7`, hardened by `c2fb2a71da` and `b1058ef9f7`.

- `test_both_export_purposes_share_one_service_and_one_bundle_schema` publishes with `PORTABLE_TRANSFER` and `SUBJECT_ACCESS`, both through `export_profile_bundle`, and asserts the on-disk payload deserialises to the same bundle schema.
- `test_distinct_purpose_metadata_is_retained_across_the_shared_service` confirms the published `ProfileBundleExportResult.purpose` differs per request while everything else about the service call is identical.
- `test_data_categories_are_derived_from_serialized_bundle_fields` and `test_carried_registry_namespaces_surface_as_derived_categories` prove `data_categories` reflects real serialized bundle fields and the coverage manifest's carried namespaces, not a static list.
- `test_every_portable_bundle_field_carries_a_declared_disclosure_classification` and `test_an_unclassified_bundle_field_refuses_instead_of_vanishing_from_the_categories` exercise the exhaustiveness guard: a genuinely unclassified field raises `ProfileExportError` rather than silently narrowing the disclosed set.
- `test_the_archive_reports_what_it_omits_not_only_what_it_carries` and `test_the_omitted_set_names_full_custody_namespaces_the_archive_cannot_carry` prove `excluded_data_categories` names the structured-custody-only namespaces (attachments, invoice evidence, event history) left out of the cleartext archive.
- `test_encrypted_transport_decrypts_to_the_canonical_cleartext_bundle` round-trips the `PASSPHRASE_ENCRYPTED` transport back to the same bundle the `CLEARTEXT_LOCAL` transport writes directly.
- `test_event_failure_keeps_target_published_and_reconcile_emits_pending_event` and `test_export_journal_directory_is_owner_only_on_posix` exercise the durability contract against real files rather than a double.

## Outcome

Both operator purposes are proven, against real filesystem state and a real serialized bundle, to share one service, one schema, and one category-derivation mechanism rather than two independently-drifting implementations.

Verified against HEAD by reading `src/cadrumo/application/user_profile/tests/test_bundle_export.py` in full and confirming all eleven tests use real `tmp_path` destinations and the real `serialize_profile_bundle`/`export_profile_bundle` call chain (no mocks, stubs, or patches). Gate: `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_bundle_export.py -m "" -q` passes as part of the combined 29-test run reported for the sibling recovery Step.

## Notes

None.
