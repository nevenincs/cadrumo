---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S16'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-lifecycle-tutorials with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Run the documented-command conformance gate and the Sphinx nitpicky build gate and ## Scope

- `fix every failure the campaign's edits caused`
- `docs src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py dev/docs/tests/test_docs_build.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the documented-command conformance gate and the Sphinx nitpicky build gate

## Scope

- `fix every failure the campaign's edits caused`
- `docs src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py dev/docs/tests/test_docs_build.py`

## Description

- Run `uv run --no-sync pytest
  src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m
  integration -q`: 62 passed - every command cited across the campaign's new
  and reworked pages resolves against the live CLI tree.
- Run `uv run --no-sync pytest dev/docs/tests/test_docs_build.py -q`
  (full-log background capture, read from disk): first pass FAILED with one
  unique warning - `The parent of a 'grid-item' should be a 'grid-row'
  [design.grid]` at the new `docs/tutorials/index.md` grid, whose colon
  fences were nested inverted (outer 3, inner 4).
- Fix the nesting (outer `::::{grid}`, inner `:::{grid-item-card}`) and
  re-run: 12 passed in 185s. Both gates green.

## Outcome

Both campaign gates are green at this commit. The reviewer-feared Sphinx
orphan trip on `docs/USERDOCS-KICKOFF-BRIEF.md` did not occur (the nitpicky
build passed with the file present); its retirement is tracked separately as
P05.S18.

## Notes

Full gate logs captured without truncation per the background-capture rule
(first-run failure list preserved on disk before slicing).
