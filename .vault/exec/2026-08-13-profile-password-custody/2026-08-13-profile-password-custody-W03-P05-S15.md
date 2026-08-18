---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:ac0154c648e9c94a743d8320727ae6339aca2b7d278f9c5bd328b8d50b0d9804'
step_id: 'S15'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Have Sol Medium review archive roots, hostile transport refusal, artifact export-import warnings and proof, restore publication, and rollback limits and ## Scope

- `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/application/user_profile/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium review archive roots, hostile transport refusal, artifact export-import warnings and proof, restore publication, and rollback limits

## Scope

- `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/application/user_profile/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Reviewed all five axes against HEAD with evidence: archive roots (`_capsule_archive.py` over the sealed-archive transport; CLI `--to` refuses an existing target); hostile transport refusal (`_sealed_archive_reader.py:104-141` — former-product suffix, non-Cadrumo suffix, first-member-must-be-header, product-marker equality, strict header parse, empty-member refusal; app-side digest-before-parse); artifact export-import warnings and proof (`_recovery_custody.py:142-178` password-proof gate, exclusive write, destination refusal, mandatory warnings; self-digest verified at model validation; restore proof re-checks profile+DEK epoch on read AND unlock); restore publication (single authority `_publish_restored_capsule` behind the restore authority; one CLI verb, `--artifact` selects the door, bootstrap-exempt with reason); rollback limits (journal-gated: rollback only while the pointer still equals `journal.pointer_before`; divergence refuses; both-stage-and-final is corruption). Ruling folded in: the producerless browse/disk-usage command contracts are RETIRED — six contract classes, the two service methods, the facade exports and both test modules deleted (precedents S104/S116/S59); `AssessBucketDeletionCommand` stays live.

## Notes

Flags recorded: (a) `export_profile_recovery_artifact` has no CLI verb at HEAD — export warnings surface only via the application API; (b) the empty-bucket browse premise no longer exists — a provisioned bucket carries the profile record and event-history rows (the removed tests asserted the old shape). Pre-existing red routed: `test_a_recorded_empty_snapshot_answers_while_an_absent_one_refuses` fails at HEAD because the seeding door now always records the empty snapshot (S188), making the absent-snapshot refuse branch unreachable through the standard fixture.
