---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:a88aa286781ab405e5a199cfce79a9a67f6d140bbd8f10d2f3044041f7775ae5'
step_id: 'S13'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

# Translate the how-to section catalogues to Catalan with full-page domain context

## Scope

- `docs/locales/ca`

## Description

- Translate the how-to section catalogues to Catalan with full-page domain context, worked across batched commits.
- Spanish-stem AEAT nouns kept invariant in the Catalan prose.

## Outcome

The `docs/locales/ca/LC_MESSAGES/how-to/**` catalogues are fully translated. Delivered across 11 commits tagged `W02.P04.S13` (representative: ce8ec7a8e7, 3713b23073, 76533113c3). Rolled into the ca language reaching 2994/2994 entries, zero untranslated, zero fuzzy at HEAD.

## Notes

Evidence reconstructed from `git log --oneline --grep "W02.P04.S13"` after delivery. Vault-only closure.
