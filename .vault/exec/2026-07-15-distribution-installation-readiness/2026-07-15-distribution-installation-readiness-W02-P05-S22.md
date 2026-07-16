---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S22'
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
     The S22 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Prove Homebrew resources hashes Python requirement commands and test block match the cohort and ## Scope

- `packaging/homebrew/tests/test_generate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove Homebrew resources hashes Python requirement commands and test block match the cohort

## Scope

- `packaging/homebrew/tests/test_generate.py`

## Description

- Build the real root and companion source distributions.
- Generate the formula twice and compare its bytes.
- Verify root and companion identities, hashes, exact dependency resources, Python requirement, both command paths, and the test block.
- Exercise rejection of renamed foreign companions and mutable release URLs.

## Outcome

- Six real-artifact integration tests passed.
- The tests exposed and repaired the macOS-arm64 `greenlet` marker split instead of widening the resource to an unsupported platform.

## Notes

- No Homebrew binary or hosted runner was used; S23 and S24 remain open.
