---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S17'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The Consolidate the four identical _bucket_id active-bucket guards onto a shared resolve_active_bucket helper and ## Scope

- `src/aeat/entrypoints/cli/_app_live_verify_cli.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Consolidate the four identical _bucket_id active-bucket guards onto a shared resolve_active_bucket helper

## Scope

- `src/aeat/entrypoints/cli/_app_live_verify_cli.py`

## Description

- Add a shared `resolve_active_bucket(active_bucket_id, *, family)` guard to
  `_app_live_auth_preflight.py`.
- Replace the four identical `_bucket_id` guard bodies (expedientes, justificante,
  notifications, verify) with one-line delegations to the shared helper; add the
  import to each (verify gains a new import).

## Outcome

Four duplicate guard bodies collapsed to one shared helper; the per-module
`_bucket_id` wrappers delegate, so 24 call sites are unchanged. 25
live-read-subgroup tests pass; ruff clean. Landed as commit `e4568c437`.

## Notes

The remaining `_verify_expected` guard in `_app_live_verify_cli.py` is a distinct
helper (different global) and is intentionally left untouched.
