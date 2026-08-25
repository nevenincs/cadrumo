---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:aacc3c17076e2e77a3de2060955cc14a5096866a692c9a3056af8c9c846054c7'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S231 M840 source-owner deferral review`

## Scope

Review S231 mixed commit `eb732c9db9` and repair `712d609bb2`: ADR ownership,
official artifacts, repeated-local facts, CRLF separation, runtime boundary, and
legacy M840 continuity failures.

## Findings

### artifact hashes | low | BOE and AEAT evidence have distinct roles

The enrolled BOE form-spec is the 56,203-byte BOE HTML artifact
`orden-hac-2572-2003.html`, SHA-256
`1b820ea36307beb67372f1eb648d865d3dd912a1c3bf9d926b8455b551f9c722`.
The separate AEAT printed declaration PDF has SHA-256
`cf3cd1a77f92d38d2668d30b378a8eca922d6a262fe82ba86f5008074001ece0`;
it is extraction evidence, not the enrolled BOE source. AEAT record design
`dr840.pdf` recomputes to
`d0348a78787db7eb767dd8093ea84773c248c0b92bcefb512972573aff34391a`.

### decision boundary | low | repaired ADR is the only normative M840 home

The deleted generic ADR was blank and unreferenced. The accepted model-scoped
M840 ADR is now the sole normative record, separates declaration/activity from
repeated local rows, and retains CRLF as generic transport rather than a source
fact. No census, binding, resolver, source owner, runtime, or M840 writer was
introduced.

### legacy continuity tests | low | five failures predate and do not regress S231

The five M840 continuity tests all fail before their assertions because their
helper requests a filing-grade snapshot from an intentionally applicability-grade
revision. This invalid fixture premise conflicts with the registry contract and
is unrelated to the documentation-only S231 commits. The M840 registry suite
passed 10 tests and Ruff passed.

## Recommendations

PASS. Retain the two-family grounding-blocked refusal and correct the legacy
continuity fixture separately to request the declared authority grade.

