---
tags:
  - '#plan'
  - '#docs-sequence-output-weight'
date: '2026-09-29'
tier: L1
related:
  - '[[2026-07-13-docs-cli-sequences-adr]]'
modified: '2026-09-29'
body_schema: body-v2
body_hash: 'sha256:fb72008e62f42b09578c384c55e603de446e52790776a3fd93bbe9e4931eab00'
---

# `docs-sequence-output-weight` plan

## Description

Approved 2026-09-29. Basis: the operator directed the compression work in this session ("carry on with subagent delegation, compression and removing superfluous repetitive data from outputs") and pre-approves all modifications.

The recorded `cli-sequence` goldens and the pages rendered from them carry large repeated outputs. The decisions are the output weight amendment (A1 to A4) of the governing docs CLI sequences ADR. S01 implements A1 and A4, S02 implements A2, S03 applies A3, and S04 regenerates the goldens through the refresh CLI, which remains their only writer. No other costly decision is involved.

## Steps

- [x] `S01` - Record setup frames as argv, exit code and captures only, bump the golden schema to 2, stop comparing setup output, and report reader outputs over 64 KiB as advisories; `dev/docs/sequences/golden_store.py, compare.py, checks.py, tests/`.
- [x] `S02` - Drop output and stderr bodies from the inline sequence payload so each output exists once in the static HTML; `dev/docs/sequence_directive.py, dev/docs/tests/test_sequence_directive.py`.
- [x] `S03` - Switch reader-facing frames to text output unless a capture, an expectation or the page's teaching needs JSON, and narrow heavy result commands; `docs/_sequences/contracts/`.
- [x] `S04` - Regenerate every golden with the refresh CLI and pass the sequence check and docs tests; `docs/_sequences/`.

## Parallelization

S01, S02 and S03 write disjoint files and run concurrently, one writer each. S03 measures candidate commands by refreshing into its own scratch goldens root, never the committed tree. S04 runs alone after all three close, because it rewrites every golden.

## Verification

- `python -m dev.docs.sequences check` passes on the regenerated goldens, and no golden stores setup output.
- The owning tests in `dev/docs/sequences/tests/` and `dev/docs/tests/` pass, including a refusal of a golden that stores setup output.
- The golden tree and the rendered sequence HTML of the Modelo 100, Renta-assembly and Modelo 390 pages are measured before and after, and both shrink.
- Sequences that cannot execute on the current tree are reported with their failure, not hidden.
