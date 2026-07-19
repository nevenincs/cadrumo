---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S17'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

# Translate the explanation and reference section catalogues to Hungarian

## Scope

- `docs/locales/hu`

## Description

- Translate the explanation and reference section catalogues to Hungarian (7 pages each section).
- Keep the generated environment-reference `(secret)`/`(derived)` sentinel markers literal rather than translated.

## Outcome

The `docs/locales/hu/LC_MESSAGES/explanation/**` and `.../reference/**` catalogues are fully translated. Delivered across commits tagged `W02.P05.S17` (886dea4929, fbdc0a6c5d, f1bcb06291, and the marker fix ebeadf96bf). Rolled into the hu language reaching 2994/2994 entries, zero untranslated, zero fuzzy at HEAD.

## Notes

Evidence reconstructed from `git log --oneline --grep "W02.P05.S17"` after delivery. Vault-only closure.
