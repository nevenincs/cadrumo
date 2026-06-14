---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S28'
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
     The S28 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Confirm the SQL secure_objects store is covered by the bucket-DEK rewrap rotation path and document or extend the rotation contract and ## Scope

- `src/aeat/adapters/persistence/storage/_rotation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm the SQL secure_objects store is covered by the bucket-DEK rewrap rotation path and document or extend the rotation contract

## Scope

- `src/aeat/adapters/persistence/storage/_rotation.py`

## Description

- Document on `default_rotation_plan` the scope boundary: it covers only the
  master-key-encrypted `*.envelope.json` file consumers; the SQL `secure_objects`
  store is intentionally excluded.

## Outcome

Confirmed (not a gap): `secure_objects` payloads are encrypted under the per-bucket
DEK (the column layer resolves the active BucketSession DEK, not the master key),
and a custody change rewraps the DEK without changing its value, so the ciphertext
never needs re-encryption on master-key rotation. 24 rotation tests green.
Committed in `4c59248e1`.

## Notes

The file-envelope consumers and the SQL store coexist for some domains; the
master-key vs bucket-DEK key split is what determines rotation membership.
