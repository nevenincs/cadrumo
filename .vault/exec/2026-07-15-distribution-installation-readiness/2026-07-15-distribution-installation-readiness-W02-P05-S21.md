---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S21'
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
     The S21 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Generate a pinned Python virtualenv formula and immutable tap snapshot from the cohort and ## Scope

- `packaging/homebrew/generate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Generate a pinned Python virtualenv formula and immutable tap snapshot from the cohort

## Scope

- `packaging/homebrew/generate.py`

## Description

- Read the exact root and companion source-distribution identities from the supplied cohort.
- Resolve the default and agent dependency closure from `uv.lock` for every declared macOS and Linux architecture.
- Generate one deterministic `Language::Python::Virtualenv` formula with immutable release and PyPI resource hashes.
- Preserve architecture-specific markers with nested Homebrew platform blocks.

## Outcome

- The generator emits one pinned tap snapshot with the root source archive, both mandatory companions, locked resources, Python 3.13, both executables, and a command-level test block.
- Mutable release URLs, foreign companion metadata, missing lock material, and unsupported platform subsets fail closed.

## Notes

- Homebrew installation and platform execution remain open under S23 and S24.
