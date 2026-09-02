---
generated: true
tags:
  - '#index'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:ac2dd6f3d032b1211d832fc15061b2f9f9b5d237d551664a3727de08fe102382'
related:
  - '[[2026-09-02-python-runtime-compatibility-P01-S01]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S02]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S03]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S04]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S05]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S06]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S07]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S08]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-summary]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S09]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S10]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S11]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S12]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S13]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S14]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S15]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S16]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S60]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S61]]'
  - '[[2026-09-02-python-runtime-compatibility-P03-S17]]'
  - '[[2026-09-02-python-runtime-compatibility-P03-S18]]'
  - '[[2026-09-02-python-runtime-compatibility-P03-S19]]'
  - '[[2026-09-02-python-runtime-compatibility-P03-S20]]'
  - '[[2026-09-02-python-runtime-compatibility-P03-S21]]'
  - '[[2026-09-02-python-runtime-compatibility-P03-S22]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S23]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S24]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S25]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S26]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S27]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S28]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S29]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S58]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S59]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S62]]'
  - '[[2026-09-02-python-runtime-compatibility-P04-S63]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S30]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S31]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S32]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S34]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S36]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S38]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S40]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S42]]'
  - '[[2026-09-02-python-runtime-compatibility-P05-S64]]'
  - '[[2026-09-02-python-runtime-compatibility-adr]]'
  - '[[2026-09-02-python-runtime-compatibility-final-review-audit]]'
  - '[[2026-09-02-python-runtime-compatibility-p01-code-review-audit]]'
  - '[[2026-09-02-python-runtime-compatibility-p02-code-review-audit]]'
  - '[[2026-09-02-python-runtime-compatibility-p03-code-review-audit]]'
  - '[[2026-09-02-python-runtime-compatibility-plan]]'
  - '[[2026-09-02-python-runtime-compatibility-research]]'
---

# `python-runtime-compatibility` feature index

Auto-generated index of all documents tagged with `#python-runtime-compatibility`.

## Documents

### adr

- `2026-09-02-python-runtime-compatibility-adr` - `python-runtime-compatibility` adr: `one source tree with an open Python floor and rolling CPython evidence` | (**status:** `accepted`)

### audit

- `2026-09-02-python-runtime-compatibility-final-review-audit` - `python-runtime-compatibility` audit: `Final implementation review`
- `2026-09-02-python-runtime-compatibility-p01-code-review-audit` - `python-runtime-compatibility` audit: `p01 code review`
- `2026-09-02-python-runtime-compatibility-p02-code-review-audit` - `python-runtime-compatibility` audit: `P02 code review`
- `2026-09-02-python-runtime-compatibility-p03-code-review-audit` - `python-runtime-compatibility` audit: `P03 code review`

### exec

- `2026-09-02-python-runtime-compatibility-P01-S01` - Change the root package floor to >=3.13 and preserve py313 static-analysis targets
- `2026-09-02-python-runtime-compatibility-P01-S02` - Regenerate lock metadata without dependency upgrades
- `2026-09-02-python-runtime-compatibility-P01-S03` - Add explicit stable and prerelease runtime records and classifier eligibility
- `2026-09-02-python-runtime-compatibility-P01-S04` - Parse and validate the runtime inventory and emit GitHub matrix JSON
- `2026-09-02-python-runtime-compatibility-P01-S05` - Add detector-teeth tests for runtime inventory gaps duplicates and invalid states
- `2026-09-02-python-runtime-compatibility-P01-S06` - Replace the stale Python ceiling assertion with the open-floor policy
- `2026-09-02-python-runtime-compatibility-P01-S07` - Update security-audit expectations for the open-ended floor
- `2026-09-02-python-runtime-compatibility-P01-S08` - Guard the exact CPython release-builder identity
- `2026-09-02-python-runtime-compatibility-P01-summary` - `python-runtime-compatibility` `P01` summary
- `2026-09-02-python-runtime-compatibility-P02-S09` - Add an AST compatibility census for removed and deprecated Python APIs
- `2026-09-02-python-runtime-compatibility-P02-S10` - Add representative-defect tests for the compatibility census
- `2026-09-02-python-runtime-compatibility-P02-S11` - Harden public annotation resolution and forward-reference behavior
- `2026-09-02-python-runtime-compatibility-P02-S12` - Exercise annotation contracts through the workspace-manifest path
- `2026-09-02-python-runtime-compatibility-P02-S13` - Harden dynamic wizard signatures against annotation representation changes
- `2026-09-02-python-runtime-compatibility-P02-S14` - Test dynamic signatures type hints metadata and CLI discovery
- `2026-09-02-python-runtime-compatibility-P02-S15` - Compile every dev and src module against the oldest supported grammar
- `2026-09-02-python-runtime-compatibility-P02-S16` - Enforce annotations as the sole project future directive
- `2026-09-02-python-runtime-compatibility-P02-S60` - Replace production TOML reading with the Python standard library
- `2026-09-02-python-runtime-compatibility-P02-S61` - Prove standard-library TOML parsing preserves the public error contract
- `2026-09-02-python-runtime-compatibility-P03-S17` - Implement isolated source and binary compatibility probes with JSON evidence
- `2026-09-02-python-runtime-compatibility-P03-S18` - Test mode separation lock binding digest binding and missing-wheel refusal
- `2026-09-02-python-runtime-compatibility-P03-S19` - Extend distribution evidence with runtime stability and installation outcomes
- `2026-09-02-python-runtime-compatibility-P03-S20` - Test source versus binary evidence and foreign cohort refusal
- `2026-09-02-python-runtime-compatibility-P03-S21` - Reuse installed-wheel isolation for selected target interpreters
- `2026-09-02-python-runtime-compatibility-P03-S22` - Verify smoke acceptance removes checkout imports and ambient executables
- `2026-09-02-python-runtime-compatibility-P04-S23` - Add stable and next source and binary compatibility matrix jobs
- `2026-09-02-python-runtime-compatibility-P04-S24` - Gate workflow inventory source mode separation skips warnings and digests
- `2026-09-02-python-runtime-compatibility-P04-S25` - Permit only the dedicated runtime matrix while preserving exact-pin lanes
- `2026-09-02-python-runtime-compatibility-P04-S26` - Enroll the compatibility workflow in change-class and fork-safety invariants
- `2026-09-02-python-runtime-compatibility-P04-S27` - Verify workflow Python calls use repository module entry points
- `2026-09-02-python-runtime-compatibility-P04-S28` - Preserve protected packaging-smoke single-build behavior
- `2026-09-02-python-runtime-compatibility-P04-S29` - Preserve protected quick-packaging single-runtime behavior
- `2026-09-02-python-runtime-compatibility-P04-S58` - Invoke clean release-cohort construction through its package module
- `2026-09-02-python-runtime-compatibility-P04-S59` - Prove clean release-cohort subprocess imports remain package-correct
- `2026-09-02-python-runtime-compatibility-P04-S62` - Scope hash enforcement without rejecting locally built cohort artifacts
- `2026-09-02-python-runtime-compatibility-P04-S63` - Prove clean cohort construction accepts digest-bound local wheels
- `2026-09-02-python-runtime-compatibility-P05-S30` - Add classifiers only for stable runtimes proven by the matrix
- `2026-09-02-python-runtime-compatibility-P05-S31` - Align manuals companion classifiers with stable runtime evidence
- `2026-09-02-python-runtime-compatibility-P05-S32` - Align official-data companion classifiers with stable runtime evidence
- `2026-09-02-python-runtime-compatibility-P05-S34` - Enforce root and companion classifier parity and prerelease exclusion
- `2026-09-02-python-runtime-compatibility-P05-S36` - Test sealed release artifacts across supported stable runtimes
- `2026-09-02-python-runtime-compatibility-P05-S38` - Document local runtime selection and source versus binary evidence
- `2026-09-02-python-runtime-compatibility-P05-S40` - Document final-runtime promotion and classifier evidence
- `2026-09-02-python-runtime-compatibility-P05-S42` - Add an inventory-driven local compatibility command
- `2026-09-02-python-runtime-compatibility-P05-S64` - Promote 3.14 classifier eligibility after source binary and artifact evidence

### plan

- `2026-09-02-python-runtime-compatibility-plan` - `python-runtime-compatibility` plan

### research

- `2026-09-02-python-runtime-compatibility-research` - `python-runtime-compatibility` research: `Python 3.13 and later compatibility evidence`
