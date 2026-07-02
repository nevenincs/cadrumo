---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S258'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace import-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S258 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.errors` and ## Scope

- `src/aeat/core/resources/_errors.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.errors`

## Scope

- `src/aeat/core/resources/_errors.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.core.resources`, `aeat.core.observability`, `aeat.core.config`, `aeat.core.corpus_manifest`, `aeat.core.json_contract`, `aeat.core.logging`, and `aeat.locales._fstring_registry` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers Phases `W02.P54`, `W02.P59`, `W02.P72` through `W02.P75`, and `W02.P81` in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 10 files as one atomic explicit-pathspec commit.

## Outcome

10 files rewritten and committed (commit `563dece0e`, `refactor(core,locales): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

Steps across `W02.P54`, `W02.P59`, `W02.P72`-`W02.P75`, and `W02.P81` are covered by this one record and this one commit, batched per the Wave dispatch brief. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
