---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:50bdc2e55d3b9b89524d34088b75e507523e9986f82db12bf3447ee59cfda322'
step_id: 'S230'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Complete every blank or fuzzy Spanish user-page translation and correct download command-list punctuation without English fallback

## Scope

- `docs/locales/es/LC_MESSAGES/`

## Description

- Translate every Spanish blank and fuzzy entry introduced by the custody docs sync.
- Preserve MCP commands, Markdown links, code spans, and PO message structure.
- Correct the three Spanish download command-list labels to use colons.
- Run Spanish completeness, dash, orphan, drift, PO parsing, localized-build, and formal review gates.

## Outcome

All ten incomplete Spanish messages now carry substantive translations with no
fuzzy markers or English fallback. The three download labels match the source
punctuation. Formal review found and then verified correction of one Spanish
serial-comma defect; final verdict passed with no open findings.

## Notes

Concurrent commit `f7fa20b713` captured the four intended catalogue files. The
final grammatical correction and S230 closure evidence land here. The Spanish
nitpicky build reached the localized pages but remains red on unrelated stale
sequence goldens, generated CLI toctree warnings, and pre-existing inconsistent
reference warnings; none originates in the translated delta.
