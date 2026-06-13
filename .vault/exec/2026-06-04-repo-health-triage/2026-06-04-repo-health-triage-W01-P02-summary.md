---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W01.P02` summary

Completed the structural import-gate phase.

- Modified: `.importlinter`
- Modified: `src/aeat/_data/corpus/test_corpus_provenance.py`
- Modified: `src/aeat/adapters/outbound/fx/_ecb_provider.py`
- Modified: `src/aeat/adapters/outbound/fx/_ecb_refresh.py`
- Modified: `src/aeat/application/user_profile/test_bundle_reexports.py`
- Modified: `src/aeat/application/workflow/test_declaration_key.py`

## Description

The absolute self-import baseline was closed. The import-linter policy now
sanctions the current real-behavior `secure_sql` test-helper edges narrowly
instead of weakening production layer rules.

## Verification

- `just audit-structure`
- `uv run --no-sync pytest src/aeat/_data/corpus/test_corpus_provenance.py src/aeat/application/user_profile/test_bundle_reexports.py src/aeat/application/workflow/test_declaration_key.py -q`
- `uv run --no-sync ruff check` on touched Python files

Evidence:

- `just audit-structure`: exit 0; import-linter reported 4 kept contracts and
  0 broken contracts.
- Focused pytest: exit 0; corpus provenance, user-profile re-export, and
  workflow declaration-key tests passed.
- Focused Ruff: exit 0; no lint findings on W01.P02 touched Python files.
