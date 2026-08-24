---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c72af5353138aa98ede4383a175b8af2dddc0dd1dcc690bff0e73b95c027d411'
step_id: 'S231'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

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
