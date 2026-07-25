---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S54'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Add target deletion assessment and reset ownership fields to bucket-maintenance contracts

## Scope

- `src/cadrumo/application/bucket_maintenance/_contracts.py`

## Description

- Add `AssessBucketDeletionCommand` as the read-only deletion-assessment intent for one explicit bucket.
- Add `BucketDeletionAssessment` carrying bucket label, lifecycle status, deletion fingerprint, and the retention floor assessment, with a validator correlating existence against metadata presence so an absent assessment cannot carry bucket metadata.
- Add the paired `reset_operation_id` and `expected_deletion_fingerprint` fields to `DeleteBucketCommand` as caller-owned operation ownership, validated to require both together or neither.
- Add `reset_operation_id` to `DeleteBucketResult` and retain `retention_override_used` so an erase performed under the legal-retention override is recorded on the result.
- Keep the retention override fields as the explicit acknowledgement pair, requiring both the flag and a non-empty reason.

## Outcome

- The contracts module now expresses deletion assessment and reset ownership as strict pydantic models, so no bucket-maintenance boundary exchanges an untyped mapping.
- Reset ownership is expressible only as a complete pair, which is the precondition the service-side ownership verification depends on.
- The absent-assessment shape is structurally prevented from carrying a fingerprint, so a caller cannot mistake a missing bucket for an assessable one.
- Landed in commit `11356b4792`, with the delete-path decomposition refinement in `f764cc53de`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The retention override remains an explicit two-field acknowledgement; no default-permissive path was introduced.
