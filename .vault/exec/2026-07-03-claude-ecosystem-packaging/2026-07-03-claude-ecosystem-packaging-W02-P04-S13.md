---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S13'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add a corpus-binary resolution seam that resolves a _data/corpus path from the aeat tree first, then the aeat_data companion package root

## Scope

- `src/aeat/core/resources/_boundary.py`

## Description

- Add the corpus-binary resolution seam to the bundled-data locator: a `_data/corpus/...` path resolves from the `aeat` package tree first, then falls back to the `aeat_data` companion package root (mirrored relative paths); a missing companion import means not-present, never an exception leak.
- Keep the single `importlib.resources` boundary discipline — the seam lives in the locator, not at call sites.
- Commit `fc0f30bd55`.

## Outcome

- Full-checkout and split-install corpus reads are uniform through one locator.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit before it could report. Gate re-verified post-hoc: the seam + companion test files pass (7 passed).
