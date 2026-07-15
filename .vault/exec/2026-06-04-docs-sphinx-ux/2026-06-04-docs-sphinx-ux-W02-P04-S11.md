---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S11'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-sphinx-ux with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-06-04-docs-sphinx-ux-plan placeholders are machine-filled by
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
     The retarget the API toctree entry to the curated overview and ## Scope

- `docs/index.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# retarget the API toctree entry to the curated overview

## Scope

- `docs/index.md`

## Description

Verified `docs/index.md` (line 210, same `64b5a8a45d` commit) retargets the root API
toctree entry to `API <api/index>` - the curated overview added by `S10` - rather than
the generated package root, so a reader following the "Reference" toctree lands on the
curated boundary map before the generated module tree.

## Outcome

Step closed. Evidence: `docs/index.md:210` reads `API <api/index>`; the target resolves
to the `S10` curated page; nitpicky Sphinx build green (see `S14`/team lead's confirmed
run) with no unresolved toctree reference at this entry.

## Notes

No new commit required for this verification; the retarget shipped in `64b5a8a45d`.
