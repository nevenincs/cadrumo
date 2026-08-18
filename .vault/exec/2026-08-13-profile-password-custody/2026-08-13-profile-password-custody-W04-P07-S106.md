---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:411ab085acefda9141016cea3d24e89b31d3d7e19c0c52dec7a1bcbe1e9f5968'
step_id: 'S106'
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
     The S106 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh close the under-declaration in the minimal profile registration helper whose signature accepts a plain string identifier while it builds a record whose identifier is UUID-constrained, so every caller passing a readable identifier fails at construction rather than at the boundary that declared the looser type, this being the same defect reached independently from two directions tonight and ## Scope

- `src/cadrumo/tests/ and src/cadrumo/application/user_profile/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh close the under-declaration in the minimal profile registration helper whose signature accepts a plain string identifier while it builds a record whose identifier is UUID-constrained, so every caller passing a readable identifier fails at construction rather than at the boundary that declared the looser type, this being the same defect reached independently from two directions tonight

## Scope

- `src/cadrumo/tests/ and src/cadrumo/application/user_profile/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

The minimal registration helper now accepts `str | UUID` and normalises through `canonical_profile_bucket_id` at the door, so a readable identifier fails with one instructive refusal at the helper boundary instead of deep inside record construction. The eight UUID-harness fixture sites were swept: bucket-maintenance browse/disk-usage fixtures adopt fixed UUIDv4 ids, and the recipient-encryption test keeps its readable/whitespace ids only as the refusal subject while the runtime bucket becomes a UUIDv4.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
