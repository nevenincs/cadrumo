---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S10'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

# Translate the how-to section catalogues to Spanish with full-page domain context

## Scope

- `docs/locales/es`

## Description

- Translate the how-to section catalogues to Spanish with full-page domain context, worked by the translation agents across batched commits.
- Spanish-stem AEAT nouns (modelo, casilla, censo, justificante) kept invariant; a follow-up fix kept the generated `(secret)`/`(derived)` markers literal in es.

## Outcome

The how-to `docs/locales/es/LC_MESSAGES/how-to/**` catalogues are fully translated. Delivered across 13 commits tagged `W02.P03.S10` (representative: b2eef0e7aa, 0cde8bc919, 5806a57a4b) plus the marker fix 472a3e94bc under S11. Verified at HEAD as part of the es language reaching 2994/2994 entries with zero untranslated and zero fuzzy.

## Notes

Evidence reconstructed from `git log --oneline --grep "W02.P03.S10"` after delivery; this record closes the step retroactively. No source or code changes.
