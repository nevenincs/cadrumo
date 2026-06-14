---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S09'
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
     The S09 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Add a row-substitution and corrupted-hash anti-tautology test proving read-time refusal and ## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a row-substitution and corrupted-hash anti-tautology test proving read-time refusal

## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/`

## Description

- Add `test_secure_object_row_substitution_fails_closed`: save two rows, copy the
  first row's ciphertext into the second via raw sqlite3, and assert
  `repo.load` raises `DecryptionError` (the substituted ciphertext fails the AEAD
  tag under the target row's identity).

## Outcome

The anti-tautology proof for H3's row-substitution gap is in place and green.
Committed in `19d1ac86e`. The pre-existing CANARY test continues to prove the
payload is ciphertext at rest.

## Notes

`load` raises on the AAD mismatch; the fail-closed `list_records` path reports the
row unreadable. The test uses `load` for an unambiguous assertion.
