---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:20d98f5b3f2e46be3abe707d3aaf0e3b0c4f17aa45e10ef6c7565d3c1506a297'
step_id: 'S231'
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
     The S231 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Complete every blank or fuzzy Catalan user-page translation and correct download command-list punctuation without English fallback and ## Scope

- `docs/locales/ca/LC_MESSAGES/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Complete every blank or fuzzy Catalan user-page translation and correct download command-list punctuation without English fallback

## Scope

- `docs/locales/ca/LC_MESSAGES/`

## Description

- Translate every Catalan blank and fuzzy entry introduced by the custody docs sync.
- Preserve MCP commands, Markdown links, code spans, and PO message structure.
- Correct the three Catalan download command-list labels to use colons.
- Run Catalan completeness, dash, orphan, drift, PO parsing, localized-build, and formal review gates.

## Outcome

All ten incomplete Catalan messages now carry substantive translations with no
fuzzy markers or English fallback. The three download labels match the source
punctuation. Formal review identified one literal false-friend rendering of
agent personas; established Catalan terminology replaced it and final review
passed with no findings.

## Notes

The Catalan completeness, dash, orphan, and PO parsing gates pass. The real
fresh-extraction drift and localized nitpicky builds currently stop before
page evaluation on unrelated registry grounding failure
`rd-1065-2007:art-42` / `a42`; this external blocker is not a catalogue defect.
