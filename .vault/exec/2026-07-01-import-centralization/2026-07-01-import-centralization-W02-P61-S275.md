---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S275'
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
     The S275 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry` and ## Scope

- `src/aeat/domain/modelos/_calculation_revision.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`

## Scope

- `src/aeat/domain/modelos/_calculation_revision.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.domain.modelos`, `aeat.domain.transactions`, `aeat.domain.attachments`, `aeat.domain.deadlines`, `aeat.domain.fincas`, `aeat.domain.invoices`, and `aeat.domain.iva` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers Phases `W02.P60`, `W02.P61`, `W02.P62`, `W02.P76`-`W02.P79` in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 9 files as one atomic explicit-pathspec commit.

## Outcome

9 files rewritten and committed (commit `1f292b29a`, `refactor(domain): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

Steps across `W02.P60`-`W02.P62` and `W02.P76`-`W02.P79` are covered by this one record and this one commit, batched per the Wave dispatch brief. This was the final W02 batch: the import-hygiene scanner's post-batch run reported 0 production sites needing facade promotion and only the 5 documented cycle-break exceptions (`application/review/_actions.py`, `application/review/_models.py`, `application/workflow/_models.py`) remaining unrewritten. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
