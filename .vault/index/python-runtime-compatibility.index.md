---
generated: true
tags:
  - '#index'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:ce39546e65839a80ab1a158b7c4168cdd9bda789d1b22a9e036fca704a293c3c'
related:
  - '[[2026-09-02-python-runtime-compatibility-P01-S01]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S02]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S03]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S04]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S05]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S06]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S07]]'
  - '[[2026-09-02-python-runtime-compatibility-P01-S08]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S09]]'
  - '[[2026-09-02-python-runtime-compatibility-P02-S10]]'
  - '[[2026-09-02-python-runtime-compatibility-adr]]'
  - '[[2026-09-02-python-runtime-compatibility-p01-code-review-audit]]'
  - '[[2026-09-02-python-runtime-compatibility-plan]]'
  - '[[2026-09-02-python-runtime-compatibility-research]]'
---

# `python-runtime-compatibility` feature index

Auto-generated index of all documents tagged with `#python-runtime-compatibility`.

## Documents

### adr

- `2026-09-02-python-runtime-compatibility-adr` - `python-runtime-compatibility` adr: `one source tree with an open Python floor and rolling CPython evidence` | (**status:** `accepted`)

### audit

- `2026-09-02-python-runtime-compatibility-p01-code-review-audit` - `python-runtime-compatibility` audit: `p01 code review`

### exec

- `2026-09-02-python-runtime-compatibility-P01-S01` - Change the root package floor to >=3.13 and preserve py313 static-analysis targets
- `2026-09-02-python-runtime-compatibility-P01-S02` - Regenerate lock metadata without dependency upgrades
- `2026-09-02-python-runtime-compatibility-P01-S03` - Add explicit stable and prerelease runtime records and classifier eligibility
- `2026-09-02-python-runtime-compatibility-P01-S04` - Parse and validate the runtime inventory and emit GitHub matrix JSON
- `2026-09-02-python-runtime-compatibility-P01-S05` - Add detector-teeth tests for runtime inventory gaps duplicates and invalid states
- `2026-09-02-python-runtime-compatibility-P01-S06` - Replace the stale Python ceiling assertion with the open-floor policy
- `2026-09-02-python-runtime-compatibility-P01-S07` - Update security-audit expectations for the open-ended floor
- `2026-09-02-python-runtime-compatibility-P01-S08` - Guard the exact CPython release-builder identity
- `2026-09-02-python-runtime-compatibility-P02-S09` - Add an AST compatibility census for removed and deprecated Python APIs
- `2026-09-02-python-runtime-compatibility-P02-S10` - Add representative-defect tests for the compatibility census

### plan

- `2026-09-02-python-runtime-compatibility-plan` - `python-runtime-compatibility` plan

### research

- `2026-09-02-python-runtime-compatibility-research` - `python-runtime-compatibility` research: `Python 3.13 and later compatibility evidence`
