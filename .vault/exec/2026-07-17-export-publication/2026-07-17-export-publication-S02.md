---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:ee10105ba8966940aa690e3b3efc9abee457e6c56d70b2f52756290b5ccdf945'
step_id: 'S02'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Persist non-secret profile export operation states atomically outside the target artifact

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_operation.py`

## Description

- Create `_bundle_export_operation.py` holding the durable, credential-free operation state for one publication.
- Declare `ProfileBundleExportOperationStatus` (prepared, completed) and the `ProfileBundleExportOperation` model carrying the resolved target identity, purpose, transport, schema version, derived categories, and UTC-validated timestamps, but no bundle bytes, passphrase, or raw tax id.
- Add `derive_export_operation_id`, a clock-free sha256 over profile, target identity, and purpose so a retried export to the same target reconciles to one journal.
- Add `ProfileBundleExportJournalRepository` persisting atomic per-file journals under `<storage-root>/profile-export-operations`, outside bucket directories, with restrictive `0700`/`0600` modes, link-like-path refusal, and `save`/`load`/`delete`/`list`/`prepared` accessors.
- Register the three journal error classes in the application error-code registry.

## Outcome

Operation-state store mirrors the proven reset-operations journal shape while staying a separate surface. Error codes bind; the package imports clean. Committed in `a9251f5fa2`.

## Notes

Journal directory name `profile-export-operations` is distinct from the reset journal and from any sealed-archive location; no reset-owned files were touched.
