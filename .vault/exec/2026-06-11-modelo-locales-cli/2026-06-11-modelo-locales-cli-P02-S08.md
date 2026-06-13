---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S08'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P02.S08 add modelo scaffold command and check mode

Scope: `src/aeat/locales/cli.py`.

## Description

- Add `python -m aeat.locales modelo scaffold`.
- Add `--check` mode that reuses coverage and drift checks without writing.
- Support `--registry-root` for contained temporary registry roots.
- Preserve existing translated leaves while adding untranslated placeholders and dropping stale leaves through the manager.

## Outcome

The locale CLI can now create and align schema-local modelo locale TOML through the managed command surface instead of direct file edits.

## Notes

Focused verification passed against a temporary registry root; committed schema locale TOML files were not edited.
