---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S20'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Repair gitignore: fix dead src/aeat corpus-manual rules, add runtime-s pattern, broaden root-level scratch patterns

## Scope

- `.gitignore`

## Description

- Retarget the dead `src/aeat/_data/corpus/manuals/**/source.pdf` ignore/exempt
  block (including the trailing `source.html/` rule) to `src/cadrumo/...`,
  matching the current package tree.
- Add a root-anchored `.runtime-*/` ignore pattern retiring the ad-hoc
  `.runtime-sNN-*` convention (existing directories are cleaned up under
  `W04.P07.S22`).
- Add narrow, root-anchored, commented safety-net patterns covering the
  currently-tracked run-artifact shapes: `/*.patch`, `/add_*.py`,
  `/scratch_*.txt`, `/*_output.txt`, `/*-snap.md`.

## Outcome

- Verified with `git check-ignore -v --no-index` that the corpus-manual
  `source.pdf` exemptions still resolve correctly under `src/cadrumo/...`
  (previously the dead `src/aeat/...` rule matched nothing, so the exemption
  block was inert).
- Verified `.runtime-*/` now matches the existing ad-hoc directories
  (`.runtime-s62-locale`, etc.).
- Verified each of the five currently-tracked repo-root run artifacts
  (`add_frontmatter.py`, `rail-snap.md`, `revert.patch`,
  `scratch_pathspec.txt`, `test_docs_output.txt`) now matches a new pattern
  via `git check-ignore -v --no-index` (the plain tracked-file check returns
  no output because git does not report ignore matches for already-tracked
  paths; removal from tracking is `W04.P07.S21`).

## Notes

None.
