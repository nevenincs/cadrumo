---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S161'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S161 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Invoke the mandatory vaultspec-documentation workflow and keep its render-and-verify gate active for this Phase and ## Scope

- `docs/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Invoke the mandatory vaultspec-documentation workflow and keep its render-and-verify gate active for this Phase

## Scope

- `docs/`

## Description

- Run the documentation phase under the structured workflow, verifying each
  page against the live command surface before changing it.
- Keep the render-and-verify gate active on every edit rather than at the end.

## Outcome

SATISFIED. The phase ran under the workflow and its verification gate stayed
live throughout, which is what this row exists to establish.

The gate is the documented-command conformance suite together with the
sequence contract, and it was run after every page change rather than once at
the close - `362 passed` on each pass, resolving every command the pages cite
against the live Click tree. No page change in this phase was committed
without it.

Grounding came from the CLI itself rather than from any document. The command
tree was materialised through the shipped lazy-subcommand path and walked with
click's `list_commands`/`get_command`, yielding 290 leaves with zero
duplicates; the naive walk that recurses over `.commands` returns ONE leaf and
completes without error, so that figure is the check that the surface was
really read. Individual verb signatures were then read from live `--help`
output, because the tree walk carries the paths but not the parameters.

The workflow's separation of research from drafting held: gathering ran
separately from authoring, and every wording change in this phase was authored
against a measured surface, not against a prior page's description of it.

Gates at HEAD `1745d216608445450dedd61fdaa0a482d0ccb1e6`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed`.

## Notes

The workflow's value showed up as two caught errors rather than as process.
A literal-string sweep of the docs tree reported four whole surfaces missing
that were fully documented - the pages cite commands through sequence
directives by name, so the pattern did not fit the data. And a count of
accepted-grammar mentions on the commands reference read as a large gap when
the page is a delegating map that scores zero by construction. Both would have
produced unnecessary rewrites.
