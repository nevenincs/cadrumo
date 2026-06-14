---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S02'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Add a strict export then import roundtrip test over the Argon2id-sealed archive with a non-default passphrase and ## Scope

- `src/aeat/application/bucket_maintenance/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a strict export then import roundtrip test over the Argon2id-sealed archive with a non-default passphrase

## Scope

- `src/aeat/application/bucket_maintenance/tests/`

## Description

- Add `test_recovery_wrap_member_records_argon2id_password_kdf` (asserts the
  member declares `argon2id` with real cost params, not HKDF) and
  `test_import_recovery_archive_rejects_wrong_passphrase` (wrong passphrase fails
  closed).

## Outcome

The Argon2id seal is asserted directly, and the existing
`test_import_recovery_archive_provisions_profile_in_fresh_root` covers the full
seal->unseal roundtrip with a non-default passphrase. 6 import/export tests green.
Committed in `d8abf5673`.

## Notes

None.
