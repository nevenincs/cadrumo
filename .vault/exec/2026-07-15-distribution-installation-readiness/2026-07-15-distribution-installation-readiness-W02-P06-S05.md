---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
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
     The S05 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Prove cohort construction is deterministic complete and non-rebuilding and ## Scope

- `dev/packaging/tests/test_release_cohort.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove cohort construction is deterministic complete and non-rebuilding

## Scope

- `dev/packaging/tests/test_release_cohort.py`

## Description

- Prove cohort construction is deterministic, complete, and non-rebuilding
  through the real integration gate.
- Run the reproducibility integration test that builds the release cohort
  twice from clean archives of the same commit and compares the frozen
  digests, and confirms consuming lanes accept the stored bytes without any
  rebuild.

## Outcome

- `dev/packaging/tests/test_release_cohort_integration.py` passed (1/1,
  586 seconds) on 2026-07-17 at source commit
  `044e48450e918648fd331072bda4767b47737d34`: two independent clean-archive
  builds produced identical member digests, and the loaded cohort re-verified
  every artifact size and SHA-256 against its manifest without rebuilding.
- The unit-scope gates in `dev/packaging/tests/test_release_cohort.py`
  (hermeticity, portable paths, undeclared-file refusal) passed 5/5 in the
  same session.

## Notes

- Determinism holds under the pinned build identity (CPython 3.13.11,
  uv 0.11.29, fixed source epoch and hash seed). The CI packaging workflows
  were pinned to the same uv version in commit `363213aee0` after the hosted
  runner's unpinned uv broke installed-digest provenance.
