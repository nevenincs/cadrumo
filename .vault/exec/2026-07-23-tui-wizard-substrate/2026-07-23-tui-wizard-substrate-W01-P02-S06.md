---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S06'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Prove the definition contract with build-time validator tests covering duplicate ids, non-forward references, literal-copy refusal, and repeating-group shape and ## Scope

- `src/cadrumo/application/flows/tests/test_definition.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove the definition contract with build-time validator tests covering duplicate ids, non-forward references, literal-copy refusal, and repeating-group shape

## Scope

- `src/cadrumo/application/flows/tests/test_definition.py`

## Description

- Author the definition build-validator suite covering every refusal arm plus positive builds and fingerprint stability/change.
- Land in commit 30e5884352 (15 tests).

## Outcome

All 15 green; reviewer confirmed coverage of every build-time validator.

## Notes

Authored by the dispatched high-executor.
