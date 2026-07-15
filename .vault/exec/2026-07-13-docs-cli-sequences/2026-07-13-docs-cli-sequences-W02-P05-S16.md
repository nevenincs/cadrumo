---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S16'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement the refresh CLI mode that re-executes sequences in the sandbox and rewrites the golden files, scoped by --page or --sequence

## Scope

- `dev/docs/sequences/__main__.py`

## Description

- Implement directive discovery in `dev/docs/sequences/__main__.py`: scan the enrolled docs pages (skipping the build, sequences-data, static, and template trees) for backtick-fenced cli-sequence directives, extract each id, options, and frame body, and parse through the shared grammar parser; unclosed fences, grammar faults (each naming the page), globally-duplicate sequence ids, and unknown `--page`/`--sequence` scopes accumulate as named problems.
- Implement `refresh_sequences` and the `refresh` CLI mode: re-execute each addressed sequence in a fresh disposable hermetic sandbox and rewrite its committed golden through the store's canonical writer; report every written path; exit 1 when any problem left the refresh incomplete.
- Ship the deferred review-p03 unused-capture disposition as `unused_capture_advisories`: a `@capture` no later frame consumes prints as a named non-failing advisory on both modes (the binding still records into the transcript and golden, so it stays review-visible).
- Drive the `python -m dev.docs.sequences` argparse surface with mutually-exclusive `--page`/`--sequence` scoping and test-visible root overrides.

## Outcome

Goldens are refreshed only through the one sanctioned CLI path (the scaffolding-CLI authority discipline); the author's git diff of the rewritten golden is the behaviour-change review. Real CLI tests drive `main()` against a real temp docs tree.

## Notes

No incidents. Page discovery is deliberately engine-owned rather than Sphinx-owned so the check tier needs no docs build; the W03 MyST directive will render the same fences this module executes.
