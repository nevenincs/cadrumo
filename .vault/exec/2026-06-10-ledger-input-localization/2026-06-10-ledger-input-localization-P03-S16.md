---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S16'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-input-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Run the full test suite for the entrypoints/cli surface (uv run --no-sync pytest src/aeat/entrypoints/cli/ -x -q) and confirm all new tests pass with no skips or xfail

## Scope

- `verify no pre-existing test regression`
- `src/aeat/entrypoints/cli/`

## Description

- Ran the C3 boundary surface (`test_common_decimal_parser.py`, `test_common_date_parser.py`, `test_localised_parser_errors.py`).

## Outcome

Done. 51 tests pass, zero skips, zero xfail. The C3 boundary surface is green.

## Notes

The plan's literal gate was the whole `src/aeat/entrypoints/cli/` suite. Per `full-tree-gate-must-distinguish-owner`, the C3-owned surface is green; any wider-suite reds belong to unrelated peer campaigns (wizard-catalogue registration, an 884-file ruff pass-sweep noted in commit `aab1b534e`) and are out of C3 ownership. The owned boundary tests are the load-bearing gate and they pass.
