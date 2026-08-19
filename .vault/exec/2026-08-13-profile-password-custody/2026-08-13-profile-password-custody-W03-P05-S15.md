---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:fc103b8114b1acb3ba3315a3ba8a58d43c699f457dfce99325bfe7b1fa732326'
step_id: 'S15'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium review archive roots, hostile transport refusal, artifact export-import warnings and proof, restore publication, and rollback limits

## Scope

- `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/application/user_profile/`

## Description

## Outcome

Reviewed all five axes against HEAD with evidence: archive roots (`_capsule_archive.py` over the sealed-archive transport; CLI `--to` refuses an existing target); hostile transport refusal (`_sealed_archive_reader.py:104-141` — former-product suffix, non-Cadrumo suffix, first-member-must-be-header, product-marker equality, strict header parse, empty-member refusal; app-side digest-before-parse); artifact export-import warnings and proof (`_recovery_custody.py:142-178` password-proof gate, exclusive write, destination refusal, mandatory warnings; self-digest verified at model validation; restore proof re-checks profile+DEK epoch on read AND unlock); restore publication (single authority `_publish_restored_capsule` behind the restore authority; one CLI verb, `--artifact` selects the door, bootstrap-exempt with reason); rollback limits (journal-gated: rollback only while the pointer still equals `journal.pointer_before`; divergence refuses; both-stage-and-final is corruption). Ruling folded in: the producerless browse/disk-usage command contracts are RETIRED — six contract classes, the two service methods, the facade exports and both test modules deleted (precedents S104/S116/S59); `AssessBucketDeletionCommand` stays live.

## Notes

Flags recorded: (a) `export_profile_recovery_artifact` has no CLI verb at HEAD — export warnings surface only via the application API; (b) the empty-bucket browse premise no longer exists — a provisioned bucket carries the profile record and event-history rows (the removed tests asserted the old shape). Pre-existing red routed: `test_a_recorded_empty_snapshot_answers_while_an_absent_one_refuses` fails at HEAD because the seeding door now always records the empty snapshot (S188), making the absent-snapshot refuse branch unreachable through the standard fixture.
