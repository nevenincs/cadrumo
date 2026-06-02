---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S170'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# for every CLI command registering --verbose assert it consumes the flag fix or remove unused declarations

## Scope

- `src/aeat/entrypoints/cli/`

## Description

Audited every `--verbose` flag declaration across
`src/aeat/entrypoints/cli/` and confirmed each consumes the flag.

## Outcome

Four `verbose: bool = typer.Option(False, "--verbose", ...)` sites,
all consumed:

- `cli/__init__.py:120` — passes `verbose` to
  `_resolve_log_level(quiet=..., verbose=verbose, debug=...)` on line
  128 (root log-level orchestration).
- `cli/_ledger.py:1799` (ledger import) — branches on
  `if verbose or verify:` at line 1865 to toggle the verification
  detail block.
- `cli/_ledger.py:1919` (ledger review) — emits `verbose` in the
  ledger-review payload at line 1969.
- `cli/_overview.py:46` — forwards `verbose=verbose` to the overview
  status builder at line 73.

No unused `--verbose` declarations detected; no removal candidates.

## Notes

The `_log_levels.py` docstring references the flag triple
(`--quiet` / `--verbose` / `--debug`); not a CLI command itself, so
no command-level audit applies to it.
