---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S14'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Run the locales scaffold and scaffold --check plus parity and honesty gates over the re-sequenced catalogue

## Scope

- `src/cadrumo/locales/`

## Description

- Run `python -m cadrumo.locales scaffold` over the re-sequenced
  catalogue (adds the four new section-title keys in all four
  catalogues, aligns the tree to every codebase key).
- Run `scaffold --check` and the repo-wide parity gate
  (`src/cadrumo/tests/test_parity.py`) to prove the four catalogues
  carry the same key set as the codebase.

## Outcome

Executed as part of the `f7a80af114` landing (same commit): parity
33/33 green; the wizard translation-resolution suite passes in every
locale. Residual `scaffold --check` output is three `flows.*`
placeholder-mismatch warnings owned by the substrate locale stream.

## Notes

Gate run performed inline with the S13 re-sequence because the two are
one atomic landing (a re-sequence without its locale sweep would break
the translation-resolution suite).

