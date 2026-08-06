---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:28ddf3ef81a9cd28eff0a170d06ee0b1e09ed5f2d3db72680f1255af2e9e9698'
step_id: 'S85'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Persist non-secret profile export operation states atomically outside the target artifact

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_operation.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD rather than a fresh edit. The predecessor profile-export-consolidation campaign landed the journal repository in commit `7b81a87b36`, hardened by `590c6cc28f` and `af82d215f8`.

- Declare `ProfileBundleExportOperation` carrying no bundle bytes and no passphrase: only the resolved target identity, purpose, transport, schema version, derived data categories, and the staged payload's SHA-256 digest.
- Root the journal directory at `<storage-root>/profile-export-operations`, a sibling of the bucket directories rather than a child of any of them.
- Assert that placement in `_validate_existing_root`, which refuses a journal root that resolves inside `buckets/` or outside the configured storage root, and refuses a symlinked or junctioned root or journal file.
- Write and replace journal files through `atomic_write_hardened_text` at file mode `0600` under a directory mode `0700`, coordinated by an `exclusive_file_lock` held on a private repository-level sidecar path.
- Derive the operation identifier clock-free, folding only the profile id, the resolved target identity, and the purpose, so a retried export to the same target for the same purpose reconciles onto the same journal instead of accreting an orphan record per attempt.
- Expose `scan()` as the isolating counterpart to `list()`: a corrupt or unreadable journal is reported rather than silently skipped, because it may still describe cleartext bundle bytes left on disk.

## Outcome

Operation-state persistence carries zero secret material and lives structurally outside every bucket's storage boundary, so a crash-recovery read of the journal directory can never itself become a confidentiality exposure, and the directory placement guard makes an accidental in-bucket journal a loud refusal rather than a silent policy breach.

Verified against HEAD by reading `src/cadrumo/application/user_profile/_bundle_export_operation.py` in full. Gate: `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_bundle_export.py src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py -m "" -q` reports 29 passed.

## Notes

None.
