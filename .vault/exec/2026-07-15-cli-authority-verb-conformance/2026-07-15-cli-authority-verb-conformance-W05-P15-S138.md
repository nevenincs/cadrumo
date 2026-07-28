---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S138'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S138 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Update root fallback write classification without accepting removed command paths and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update root fallback write classification without accepting removed command paths

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`

## Description

- Read the root fallback write guard module and enumerate its assertions.
- Confirm the guard classifies write paths without accepting any removed command path.
- Run the module and confirm it passes with no marker filter and no parallel deselection.

## Outcome

The named surface already classifies root fallback writes without accepting a removed command path, and does so structurally rather than by listing forbidden strings: it asserts that every guarded write path names a live command, which makes accepting a removed path impossible without failing.

That assertion carries its own anti-tautology proof, which confirms a stale catalogue entry is rejected, so the guard is not vacuous. The module also proves the guard leaves read and recovery paths open and that the CLI root delegates route classification to the backend policy rather than duplicating it. The module runs green under an explicit empty marker expression and without parallelism, so no lane was silently deselected.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
