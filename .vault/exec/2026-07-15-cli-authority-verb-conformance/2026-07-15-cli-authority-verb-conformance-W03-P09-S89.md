---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S89'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove restrictive temporary permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events

## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD rather than a fresh edit. The predecessor profile-export-consolidation campaign landed the eighteen real-behaviour recovery tests in commit `ac097a53a7`, hardened by `5aac909a78`, `a3a0219bd5`, `c2fb2a71da`, `b1058ef9f7`, `af82d215f8`, and `565d0e1ee0`.

- `test_prepared_staged_temp_is_restrictive_and_unpublished` and `test_a_crash_before_the_journal_lands_leaves_no_unreachable_cleartext` prove the restrictive-temp-file and journal-before-stage ordering against real file permissions.
- `test_same_target_export_is_excluded_while_the_target_lock_is_held` and `test_reconcile_skips_a_prepared_operation_whose_target_lock_is_held` prove same-target mutual exclusion between two concurrent real export/reconcile invocations.
- `test_crash_before_replace_reconciles_as_prepared_with_no_completion_event` and `test_crash_after_replace_reconciles_to_a_completed_event_via_the_content_digest` cover the two sides of the replace crash window: an unpublished orphan clears silently, a published-but-uncommitted operation reconciles to the emitted event via the content digest.
- `test_reconcile_completion_is_idempotent_for_a_published_operation`, `test_digest_matched_reconcile_leaves_no_cleartext_staged_temp`, and `test_completed_export_leaves_no_journal_and_one_event` prove reconciliation never double-emits and always ends with exactly one durable event and zero leftover cleartext.
- `test_export_publishes_into_a_freshly_created_parent_directory` proves `fsync_parent_dir` durability against a destination whose parent did not exist before the export.
- `test_a_later_export_clears_a_crashed_run_orphan_journal_and_cleartext_temp`, `test_re_exporting_to_the_crashed_target_clears_its_orphan_before_reusing_the_journal`, and `test_a_later_export_emits_the_owed_event_for_a_crash_published_bundle` prove the fresh-process reconciliation sweep that `export_profile_bundle` runs before every publication recovers a genuinely prior process's crash, not just an in-process simulated one — three tests use `os._exit` or `child.kill()` to hard-kill a real subprocess mid-publication.
- `test_a_corrupt_journal_does_not_starve_the_healthy_operation_behind_it` and `test_an_unfinalisable_operation_does_not_starve_the_one_behind_it` prove per-operation isolation in the reconciliation walk.
- `test_reconcile_removes_the_hardened_writers_own_inner_temp` and `test_a_journal_that_vanishes_mid_scan_is_a_skip_not_a_failure` cover the hardened writer's own inner staging temp and a benign scan-then-vanish race.

## Outcome

No premature `PROFILE_EXPORTED` event is ever proven possible for an unpublished bundle, and no durably-published bundle is ever proven left without its event, across every real crash window the service can hit.

Verified against HEAD by reading `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py` in full and confirming three tests hard-kill a real spawned subprocess (`os._exit` / `child.kill()`) rather than simulating the crash in-process. Gate: `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_bundle_export.py src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py -m "" -q` reports 29 passed in 104.88s.

## Notes

None.
