---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S86'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Implement one locked target serialization with restrictive temporary files, file fsync, durable PREPARED state, atomic replace, parent-directory fsync, post-publish COMPLETED event, and honest PREPARED recovery

## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD rather than a fresh edit. The predecessor profile-export-consolidation campaign landed the publication service in commit `a9251f5fa2`, hardened by `5aac909a78`, `a3a0219bd5`, `c2fb2a71da`, `b1058ef9f7`, `af82d215f8`, and `565d0e1ee0`.

- Hold one `exclusive_file_lock(request.destination)` across the whole publication in `export_profile_bundle`, so a concurrent export to the same file is excluded end to end.
- Journal the `PREPARED` operation record BEFORE any cleartext bundle byte reaches disk in `prepare_profile_export`, naming the staged path the write is about to create; this closes a prior window (`565d0e1ee0`) in which staging preceded the journal write and a crash inside it stranded an unreachable cleartext bundle.
- Stage the serialized payload through `atomic_write_hardened_bytes` (`O_EXCL`, mode `0600`, fsync, atomic create) to a restrictive sibling temp file, discarding the journalled operation on any staging failure.
- Publish in `publish_prepared_export` by `os.replace` onto the destination, then `fsync_parent_dir`, then transition the journal to `COMPLETED`, and only after that emit the `PROFILE_EXPORTED` completion event.
- Never un-publish on a post-replace failure: if the completion event cannot be written, the `COMPLETED` journal is left in place for a later reconciliation to emit the pending event, rather than rolling back a bundle that is already durably on disk.
- Derive the completion event from the operation's fixed `event_occurred_at`, so a live emission and a later reconciliation emission produce the byte-identical, idempotent `event_id`.
- Recover honestly in `reconcile_prepared_exports`: a `COMPLETED` operation or a `PREPARED` operation whose destination content matches the recorded digest is treated as durably published (event emitted, journal cleared); a `PREPARED` operation with no matching content is a genuine orphan (staged temp removed, journal cleared, no event emitted).
- Run reconciliation before every publication's own target lock is acquired, since reconcile takes each target lock non-blocking and would otherwise skip the very in-flight-looking crash orphan it exists to clear.

## Outcome

The three-phase sequence (journal PREPARED, stage, replace, journal COMPLETED, emit event) has no window in which a durably-published bundle is left without its audit event or in which a genuinely unpublished bundle is reported as complete; every crash window resolves deterministically from the journal plus a content-digest comparison against the live destination.

Verified against HEAD by reading `src/cadrumo/application/user_profile/_bundle_export.py` in full. Gate: `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_bundle_export.py src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py -m "" -q` reports 29 passed in 104.88s.

## Notes

None.
