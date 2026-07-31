---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:14d62ee304d01764a4adab4558b189958eb48c4a8fe0ebadc1def724ec09a6d1'
step_id: 'S16'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

# Translate the how-to section catalogues to Hungarian with full-page domain context

## Scope

- `docs/locales/hu`

## Description

- Translate the how-to section catalogues to Hungarian with full-page domain context, worked across batched commits.
- Spanish-stem AEAT nouns kept invariant in the Hungarian prose.

## Outcome

The `docs/locales/hu/LC_MESSAGES/how-to/**` catalogues are fully translated. Delivered across 11 commits tagged `W02.P05.S16` (representative: e4d40357da, 19f033fb90, 1ec9c7411b). Rolled into the hu language reaching 2994/2994 entries, zero untranslated, zero fuzzy at HEAD.

## Notes

Evidence reconstructed from `git log --oneline --grep "W02.P05.S16"` after delivery. Vault-only closure.
