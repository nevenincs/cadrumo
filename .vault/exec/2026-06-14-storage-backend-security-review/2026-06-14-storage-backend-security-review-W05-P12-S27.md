---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S27'
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
     The S27 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Delete the v1 portable-bundle compat branch and drop version 1 from the supported set per no-legacy-compatibility and ## Scope

- `src/aeat/application/user_profile/_bundle.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the v1 portable-bundle compat branch and drop version 1 from the supported set per no-legacy-compatibility

## Scope

- `src/aeat/application/user_profile/_bundle.py`

## Description

- Drop `1` from `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` (now `{2}`), delete the
  now-unreachable `if bundle_schema_version == 1` facts-only branch in
  `deserialize_profile_bundle`, and rewrite the v1-rationale docstrings/comments
  in `_bundle.py` and `_portable_export.py` to the v2-only reality.

## Outcome

The v1 portable-bundle compat path is deleted, not bridged, per the ADR
adjudication that `no-legacy-compatibility` supersedes the 2026-05-27 portability
ADR's v1-importable clause (pre-beta, no released bundles, no writer emits v1). A
v1 bundle is refused by the supported-version gate. 24 bundle/lifecycle/export
tests green. Committed in `fbffabc98`.

## Notes

The empty-tuple field defaults remain — they model a category with no rows, not
v1 compatibility.
