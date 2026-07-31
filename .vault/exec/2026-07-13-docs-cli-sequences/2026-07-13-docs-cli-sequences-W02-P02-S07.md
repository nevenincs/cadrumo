---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:c6c282847752063e34bdca1d449a2aa1d3fe05ced60db9fabfa1848748831860'
step_id: 'S07'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

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
