---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S02'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P01.S02 implement contained registry-root resolution

Scope: `src/aeat/locales/_modelo_manager.py`.

## Description

- Add the manager path authority for the bundled AEAT registry root.
- Resolve directory-mode modelos and revision directories before write targets are accepted.
- Reject path-like modelo and revision identifiers before joining registry paths.
- Resolve schema-local locale TOML targets below the contained registry root.

## Outcome

Modelo schema-local write targets now resolve through a single manager that constrains writes to the registry modelo tree. The later CLI commands can reuse this path authority for audit, scaffold, set, remove, and coverage operations.

## Notes

Focused verification passed for a real bundled M130 revision locale target, a traversal refusal, and `ruff check`.
