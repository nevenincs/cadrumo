---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2e0c1ef9cdcdc349b1043204607306db8f3fadef8284f14f3e4792898801dbd6'
step_id: 'S23'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---
# Reconcile post-close user-documentation catalogue drift across Spanish, Catalan, and Hungarian by synchronizing the seven source-divergent pages, translating every incomplete entry across the current thirty-page backlog, and proving the full completeness and fresh-POT equality gates return zero without excluding a page or accepting fuzzy fallback

## Scope

- `docs/locales/{es,ca,hu}/LC_MESSAGES; dev/docs/tests/test_docs_localization.py; dev/docs/tests/test_docs_catalogue_drift.py`

## Description

- Re-extract the user-documentation POT set through the canonical docs i18n pipeline.
- Reconcile the finite Modelo revision-locale parity prerequisites exposed by
  Sphinx before POT comparison, using the canonical locale revision-move and
  set verbs rather than parallel tables.
- Complete the 35 current translations in each of Spanish, Catalan, and
  Hungarian with page context and preserved code, command, link, anchor, and
  interpolation literals.
- Run the complete per-language completeness, fresh-POT equality, and Modelo
  revision-locale parity gates without exclusions or fuzzy fallback.

## Outcome

Closed. Later canonical catalogue synchronization had already retired the old
30-page checkpoint. Fresh execution found 35 real incomplete messages in each
language across 14 how-to catalogues. All 105 are now translated, non-fuzzy,
and structurally faithful. The resulting delta is exactly 42 PO files.

The fresh-POT build initially exposed committed Modelo revision-locale drift
before reaching PO comparison. M038, M182, M187, M220, and M763 were reconciled
through the canonical locale CLI with no registry or duplicate locale authority.
The parity gate is now green and the POT comparison reaches and validates the
translated catalogues.

## Notes

- Completeness: 3 passed in 2.83 seconds.
- Fresh-POT equality: 3 passed in 101.72 seconds.
- Modelo revision-locale parity: 10 passed in 11.34 seconds.
- Independent review parsed all 105 changed entries and found zero empty,
  fuzzy, unchanged-source-copy, backtick/command, Markdown-link, anchor, or
  interpolation mismatches. `git diff --check` was clean.
- Translation commit: `02408fa4df`.
