---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S07'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Implement :seed: recipe inlining that prepends a shared @setup fragment from the named seed file before the sequence's own frames and ## Scope

- `dev/docs/sequences/_seeds.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement :seed: recipe inlining that prepends a shared @setup fragment from the named seed file before the sequence's own frames

## Scope

- `dev/docs/sequences/_seeds.py`

## Description

- Add `_seeds.py` implementing `load_seed_frames`, which reads a named recipe from the committed `docs/_sequences/seeds/<name>.seq` tree and parses it through the shared frame-line pass with a `seed:<name>` source label.
- Enforce the seed-only constraint of ADR ruling D6: a recipe may hold only `@setup` frames, so a visible command or a `@result` frame in a recipe is refused.
- Report a missing or unreadable recipe as an instructive accumulated problem rather than a silent skip or a crash.
- Wire `parse_sequence` to inline the recipe's setup frames before the body's own frames when `:seed:` is present, so seed captures thread into body placeholders.

## Outcome

Shared setup is declared once and inlined as executed, collapsed `@setup` truth. A missing recipe names its resolved path; a recipe with a non-setup frame names the offending recipe line. Seeding never introduces undocumented state.

## Notes

`_seeds.py` imports the shared line parser from `_parser.py`, and `parse_sequence` defers its import of `_seeds` to break the module cycle. The default seeds root resolves relative to the module so recipes are found regardless of the process working directory.
