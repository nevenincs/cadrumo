---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S19'
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
     The S19 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Verify the whole engine test suite (parser, runner, comparison, CLI, anti-tautology) passes green with no mocks or skips and ## Scope

- `dev/docs/sequences/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the whole engine test suite (parser, runner, comparison, CLI, anti-tautology) passes green with no mocks or skips

## Scope

- `dev/docs/sequences/tests`

## Description

- Run the whole engine suite — parser and seeds (unit), runner, golden store and comparison, refresh/check CLI, and the executor-level mask-honesty gate (integration) — in one pass: 89 tests green.
- Confirm ruff lint, ruff format, and ty type-check clean across `dev/docs/sequences/` and `dev/docs/tests/test_sequence_goldens.py`.
- Confirm the suite carries no mocks, stubs, patches, skips, or xfail markers: every integration test executes the real CLI in a real-crypto hermetic sandbox; every divergence case mutates a real committed artifact or a real envelope document.

## Outcome

The W02 execution engine is complete and green end to end: grammar parsing, hermetic execution with capture threading, committed goldens, masked comparison with live semantic expectations, the CLI-owned refresh/check surface, and the anti-tautology gate — the foundation W03's two build-gate surfaces wire onto without re-implementing anything.

## Notes

Peer WIP observed but untouched during this phase: uncommitted docstring-example edits in `dev/docs/sequences/_golden_store.py` and a staged `docs/tutorials -> docs/how-to` page move belong to a concurrent docs campaign; explicit-pathspec commits kept them out of this feature's history.
