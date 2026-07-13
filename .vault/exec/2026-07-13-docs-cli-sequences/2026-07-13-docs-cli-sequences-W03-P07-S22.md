---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S22'
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
     The S22 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Implement the Python tokeniser against the materialised Click tree, classifying executable, verb path, option, option value, positional value, and interpolated placeholder tokens with a command-path key on each verb token and ## Scope

- `dev/docs/sequences/_tokeniser.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the Python tokeniser against the materialised Click tree, classifying executable, verb path, option, option value, positional value, and interpolated placeholder tokens with a command-path key on each verb token

## Scope

- `dev/docs/sequences/_tokeniser.py`

## Description

- Add `_tokeniser.py` to the sequence engine: a build-time classifier that tokenises a frame's argv against the materialised Click tree.
- Materialise the tree once, cached, reusing the CLI-reference substrate (force lazy subtrees, name the root, walk to a node index) so the token grammar binds to the same tree the help projection is built from.
- Duck-type option params on the Click param kind rather than `isinstance`: Typer vendors its own Click fork, so a `TyperOption` is not the installed `click.Option`, and an isinstance check silently classifies every value option as a flag.
- Classify each token as executable, group verb, leaf verb, option, option value, positional argument, or interpolated `{name}` placeholder; carry the space-joined command-path key on the executable, every verb token, and each option token.
- Consume a value-taking option's following token as its option value, unless that token is itself a `{name}` placeholder; degrade an unresolved bare token to a positional argument so an unknown verb never raises.

## Outcome

- The tokeniser classifies real command lines correctly against the live tree (verified with `app modelo work create/calculate/verify`, `app ledger import --file`, inline `--format=json`, and threaded `{name}` placeholders).
- The command-path key is the space-joined path including the leading `aeat` token, byte-identical to the `cli-tree.json` projection keys the frontend widget resolves against, so hover-help is reconciled with the projection with no adapter.
- Ruff and ty are clean.

## Notes

- Materialising the tree needs an isolated storage root and English output pinned (the reference-generator environment); a bare interpreter with a stale retired-product database in the default storage root raises before the walk. The docs build already sandboxes storage, so the directive path is unaffected.
