---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:e6117d14192452007457a6e945bedd1864f09f46dc26547ebe89ba10d1462117'
step_id: 'S03'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

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
  `dev/packaging/python_cohort.py`); the focused cohort gates passed 5/5 across `dev/packaging/tests/test_python_cohort.py` and `dev/packaging/tests/test_release_cohort.py` combined, and
  the full reproducibility integration proof passed afterwards.

## Notes

- The first build attempt failed loudly and correctly on the undeclared
  `python/.gitignore` — evidence the completeness refusal works. No inventory
  weakening was applied; the transient file is removed at its source.
