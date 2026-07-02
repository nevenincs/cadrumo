---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S174'
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
     The S174 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`, `aeat.domain.user_profile` and ## Scope

- `src/aeat/application/user_profile/_aggregate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`, `aeat.domain.user_profile`

## Scope

- `src/aeat/application/user_profile/_aggregate.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.application.user_profile`, `aeat.domain.user_profile`, and `aeat.domain.contribuyente` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. Also completed the `aeat.core.parsing` precondition-promotion sweep by hand: routed the remaining `_parse_bool` / `_parse_iso8601_date` call sites in `aeat.domain.user_profile._values`, `aeat.domain.contribuyente.family`, and `aeat.domain.contribuyente._descendant_facts` onto the already-public `parse_bool` / `parse_iso8601_date` facade names (these were classified as "needs facade promotion" by the scanner because the private and public names differ, but the public names already existed — no new `__all__` entry was needed). This record anchors and covers Phases `W02.P41`, `W02.P55`, and `W02.P56` in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Hand-rewrote the `_parse_bool` / `_parse_iso8601_date` sites onto their public aliases in `domain/user_profile/_values.py`, `domain/contribuyente/family.py`, `domain/contribuyente/_descendant_facts.py`, `domain/contribuyente/__init__.py` (isolated from an unrelated peer WIP addition in the same file via a HEAD-anchored own-only patch and `git apply --cached`).
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 19 files as one atomic explicit-pathspec commit.

## Outcome

19 files rewritten and committed (commit `176dbebd1`, `refactor(user_profile,contribuyente): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

Steps across `W02.P41`, `W02.P55`, and `W02.P56` are covered by this one record and this one commit, batched per the Wave dispatch brief. The `aeat.domain.contribuyente/__init__.py` working-tree copy also carried an unrelated peer addition (`parse_descendiente_flag` promotion) at commit time; the apply-cached gated drive isolated only my own hunks so the peer's in-flight edit was left untouched in the working tree. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
