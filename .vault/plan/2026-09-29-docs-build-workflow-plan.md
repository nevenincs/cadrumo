---
tags:
  - '#plan'
  - '#docs-build-workflow'
date: '2026-09-29'
tier: L1
related:
  - '[[2026-09-29-docs-build-workflow-adr]]'
  - '[[2026-07-13-docs-cli-sequences-adr]]'
modified: '2026-09-30'
body_schema: body-v2
body_hash: 'sha256:59c5cc4e39999774ae554657b0998fd1401233db1d254b6300e1a0e625c4079e'
---

# `docs-build-workflow` plan

## Description

Approved 2026-09-29. Basis: the operator directed this session to act on every docs build and API recommendation, and pre-approves all modifications.

The decisions are D1 to D4 of the docs build workflow ADR; the goldens stay governed by the docs CLI sequences ADR. S01 implements D1, S02 D2, S03 D3 and S04 D4, and S05 verifies and opens the pull request from the `fix/docs-json` branch.

## Steps

- [x] `S01` - Refuse sequence refresh, check and coherence on a stale local authority, naming the republish command; `dev/docs/sequences/`.
- [x] `S02` - Select the committed-goldens gate in the merge gate for docs, dev/docs and source changes, with a runner-persistent verdict cache; `dev/ci/change_scope.py, .github/workflows/`.
- [x] `S03` - Preview a page or a directory from committed goldens with a persistent doctree cache, and stop classifying docs-serve as a partial build; `dev/docs/build.py, dev/docs/serve.py, docs/conf.py, justfile`.
- [x] `S04` - Generate API stubs at build time, remove them from git, and guard the admitted module set with an independent derivation; `docs/conf.py, dev/docs/apidocs/, docs/api/, .gitignore, justfile`.
- [x] `S05` - Run the full docs build and owning gates, then open the pull request; `docs/, dev/docs/`.

## Parallelization

S01 and S02 write disjoint files and run concurrently with the S03 and S04 worker. S03 and S04 share `docs/conf.py`, `dev/docs/build.py` and `justfile`, so one worker takes them in order. S05 runs alone after all of them close.

## Verification

- The sequence engine refuses a stale authority, proven on an isolated fixture, and passes on a current one.
- The merge-gate change-scope tests prove that docs, dev/docs and source changes select the goldens gate.
- A page preview and a directory preview render without executing sequences, and a repeated preview reuses its doctree cache.
- A full build generates the API stubs, the independent derivation test passes, and no `docs/api/*.rst` remains tracked.
- `just docs-build`, `python -m dev.docs.sequences check`, the docs and sequence test suites, lint and types all pass.
