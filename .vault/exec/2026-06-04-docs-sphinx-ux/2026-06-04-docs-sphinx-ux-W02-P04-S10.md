---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S10'
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
     The S10 and 2026-06-04-docs-sphinx-ux-plan placeholders are machine-filled by
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
     The add a curated API boundary overview and ## Scope

- `docs/api/index.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add a curated API boundary overview

## Scope

- `docs/api/index.md`

## Description

Verified `docs/api/index.md` landed via commit `64b5a8a45d` as the curated Python API
boundary overview: a contributor-facing "Python API overview" page describing the
hexagonal layer boundaries (`cadrumo.core`, `cadrumo.domain`, `cadrumo.application`,
`cadrumo.adapters`, `cadrumo.entrypoints`) and a "Where to start" reading order, each
layer cross-linked with `{doc}` roles into the generated module reference. Confirmed
`python -m dev.docs.apidocs scaffold --check` reports "Stub tree is conformant. No
drift detected." - the curated page sits outside the CLI-owned generated `*.rst` stub
set and does not conflict with it.

## Outcome

Step closed. Evidence: `docs/api/index.md` present at HEAD with the curated overview
content; apidocs scaffold conformance clean; nitpicky Sphinx build green including this
page (see `S14`/team lead's confirmed run).

## Notes

No new commit required for this verification; the page itself shipped in `64b5a8a45d`.
