---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-installation-readiness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Build wheel sdist companions plugin MCPB Scoop and Homebrew members once from a clean archive and ## Scope

- `dev/packaging/release_cohort.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Build wheel sdist companions plugin MCPB Scoop and Homebrew members once from a clean archive

## Scope

- `dev/packaging/release_cohort.py`

## Description

- Build every release member once from one clean Git archive of the tagged
  source commit through the immutable cohort builder.
- Correct the builder defect that poisoned the completeness check: the `uv`
  build tool seeds its output directory with a `.gitignore` that the cohort
  manifest legitimately does not declare; the python-cohort assembly now
  removes that build-tool artifact before inventory freeze.
- Rebuild the complete cohort after the fix and verify the frozen inventory.

## Outcome

- First complete immutable release cohort assembled on 2026-07-17: cohort id
  `616f48fcc2a748349cbfccb48952499523d3de82ad5ced1f5ec664b67024e16f`, version
  `0.2.1`, source commit `044e48450e918648fd331072bda4767b47737d34`, containing
  the root wheel and sdist, both data-companion wheels and sdists, the python
  cohort manifest, the Claude plugin and marketplace archives, the MCPB bundle,
  the Scoop manifest, the Homebrew formula, and the release manifest — all
  digest-bound, with no undeclared file.
- The builder defect fix landed as commit `044e48450e` (one file,
  `dev/packaging/python_cohort.py`); the focused cohort gates passed 5/5 and
  the full reproducibility integration proof passed afterwards.

## Notes

- The first build attempt failed loudly and correctly on the undeclared
  `python/.gitignore` — evidence the completeness refusal works. No inventory
  weakening was applied; the transient file is removed at its source.
