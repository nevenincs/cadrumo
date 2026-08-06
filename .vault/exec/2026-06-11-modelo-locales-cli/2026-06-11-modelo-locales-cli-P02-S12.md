---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:0bba6472f92f8836a2b41c67549ce2fa95d67a7d6f544d807a92aca29c2c33ae'
step_id: 'S12'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P02.S12 localize modelo CLI help and diagnostics

Scope: `src/aeat/locales`.

## Description

- Enroll modelo CLI help and diagnostics in the ordinary locale catalogue.
- Replace dynamic modelo drift diagnostic lookup with static `tr(...)` call sites so scaffold and audit can see the keys.
- Populate the new CLI strings for `en`, `es`, `ca`, and `hu` through `python -m aeat.locales set`.
- Keep schema-local TOML untouched during CLI-surface localization.

## Outcome

The modelo locale command surface now has localized Typer help and translated diagnostics for scaffold, set, remove, coverage, missing drift, and stale drift messages.

## Notes

Focused verification passed for `ruff check` on the touched locale modules and for `python -m aeat.locales modelo coverage/audit en 130 2019-y-siguientes`. Generic locale audit/scaffold check passed after key enrollment, then a later fresh `scaffold --check` run was blocked by an unrelated active worktree import regression in `application/filing/_export.py` (`re` referenced without import).
