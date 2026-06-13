---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S03'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P01.S03 implement TOML load and write preservation

Scope: `src/aeat/locales/_modelo_manager.py`.

## Description

- Add schema-local TOML loading for `[labels]` and `[help]` tables.
- Return empty translation-file models for missing locale targets when strict existence is not requested.
- Add deterministic TOML writing with sorted string leaves.
- Preserve existing translated leaves through parsed translation-file models rather than rebuilding from schema text.

## Outcome

The manager can now read and write the same registry-local locale TOML shape consumed by the runtime loader. Future scaffold and set operations can update translated leaves through this contract instead of direct file edits.

## Notes

Focused verification parsed a committed M130 locale file, wrote a temporary registry-local locale file, re-parsed it with `tomllib`, and passed `ruff check`.
