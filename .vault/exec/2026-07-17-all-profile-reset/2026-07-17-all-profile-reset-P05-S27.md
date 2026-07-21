---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S27'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace all-profile-reset with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S27 and 2026-07-17-all-profile-reset-plan placeholders are machine-filled by
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
     The Migrate the reset family help and risk metadata to the accepted grammar and ## Scope

- `src/cadrumo/application/operator_surface/_help.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the reset family help and risk metadata to the accepted grammar

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Add `config reset start --yes`, `config reset status`, and `config reset resume --yes` entries to the curated config help surface (`_help.py`) diagnostics section, alongside `repair quarantine` / `repair reset-progress`.
- Risk metadata for `config.reset.start` / `.status` / `.resume` was already migrated to the accepted grammar in S26 (`_risk_table.py`); confirmed start/resume are `destructive=True` and status is read-only, no stale flat `config.reset` entry remains.

## Outcome

The reset lifecycle is discoverable on the operator help surface with confirmation flags shown, matching sibling destructive verbs. Harness rule-surface conformance, documented-command conformance, and operator-surface suites green (354 passed). Locale keys wired in S28 (co-committed).

## Notes

Help descriptions reuse the accepted reset verb copy; new keys `cli.operator_surface.help.config.reset_{start,status,resume}` are wired through the locales CLI in S28.
