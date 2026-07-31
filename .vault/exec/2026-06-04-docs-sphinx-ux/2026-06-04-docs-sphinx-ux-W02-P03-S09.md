---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:85db9f3d40cd47dd45c353ef690cdaa987915bb6610e749c988fde5ddc292686'
step_id: 'S09'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# preserve hidden toctrees while exposing visible route labels

## Scope

- `docs/index.md`

## Description

Verified `docs/index.md` carries eight `:hidden:` toctree blocks (lines 116 onward),
each with a `:caption:` (Your profile, Your calendar, Your ledger, Your filings, Help,
Reference, How it works, Project) and human-readable link labels (e.g. "Set up a
profile <how-to/profile-setup>") rather than bare file paths, so the sidebar renders
labeled, grouped routes while the toctrees stay out of the body flow.

## Outcome

Step closed as already-satisfied. No new commit required; this record documents the
verification only.

## Notes

Read `docs/index.md` at HEAD and confirmed every hidden toctree entry pairs a
human-readable label with its target document.
