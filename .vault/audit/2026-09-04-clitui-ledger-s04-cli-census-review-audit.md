---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:227f8fa0c3d021bf6711b848e3872420f66282720dfd7608868b39812bd5701b'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
---

# `clitui-ledger` audit: `S04 CLI denominator census review`

## Scope

Mandatory independent review of `W01.P02.S04`, bound to source trace
`3e642ad9ee` and the current source digest
`sha256:4a7ebd8cf910b1f10851934d19320d1bc57890f86c3f482d87c7f696e8a214ef`.
The review covered the complete `LEDGER_CLI_COMMAND_CENSUS` projection, its
hand-authored ownership and sub-operation annotations, the production
`CommandSpec` graph, deferred handlers and result schemas, the capability
matrix contract, the campaign ADR/research/plan/reference, and the existing
command-spec tests.

The live projection independently reproduced 91 Ledger graph nodes, 77 leaves,
14 groups, the one executable `participation` group, 78 invocables, 45 declared
supplemental sub-operations, ownership counts of 44 `policy-bearing`, 27
`mixed`, and 7 `transport-only`, and 78 `TuiCapability.NOT_IMPLEMENTED`
declarations. Every census path, handler identity, schema identity, and TUI
posture equals its owning production `CommandSpec`. Isolated mutations proved
that the implementation code refuses a new unannotated endpoint, unknown and
missing annotations, duplicate annotation and invocable identities, duplicate
sub-operation identities, and unavailable handler or schema declarations.
The four focused command graph/spec suites passed 30 tests; Ruff lint and `ty`
passed for the source. The acceptance ruling is **NOT ACCEPTED** because the
blocking findings below mean the S04 stream is not yet a complete, durable,
quality-gated denominator.

## Findings

### census-detector | high | The new declaration gate has no durable defect-detection tests

No test imports `LEDGER_CLI_COMMAND_CENSUS`, `LedgerCliCensusAnnotation`, or
`_validated_annotations`. The 30 passing command-spec tests validate the
underlying generic graph, but none proves that this new census rejects a newly
enrolled Ledger endpoint without ownership adjudication, a missing or unknown
annotation, duplicate endpoint or sub-operation identities, or an unavailable
handler/schema at the census boundary. Ad hoc isolated mutation probes showed
the current code refuses those representative defects, but an interactive
probe is not a durable gate and cannot protect later edits. Under detector
teeth and no-silent-under-declaration, this is a blocking `HIGH`: the exact
existing owner is `src/cadrumo/entrypoints/cli/tests/test_command_specs.py`,
whose stated responsibility is the complete shipped command authority.

### suboperation-underdeclaration | high | Bulk CSV classification is absent from the claimed complete census

`ledger_classify` dispatches `--file` requests to the distinct
`ledger_classify_bulk_csv` batch workflow, while the annotation lists only
`ledger.classify.direct` plus M210, IVA derivation, model-assisted, evidence,
and auto-split modes. A multi-row CSV classification workflow has different
input, result, failure, and batch semantics from direct single-transaction
classification, so folding it into `direct` contradicts the document's
behavior-distinct criterion. The published count of 45 therefore silently
under-declares at least `ledger.classify.bulk_csv`; S04 cannot call the CLI
stream complete until all overloaded-handler branches are re-adjudicated.

### source-format-gate | high | The reviewed production source fails the formatter check

`ruff format --check` reports that
`src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py` would be reformatted
at the `_validated_annotations` block. Ruff lint and `ty` pass, but the project
quality rule explicitly bars completion when a change introduces a formatting
failure. The published source digest faithfully names the currently failing
file; it does not waive the gate.

### stable-identity-validation | medium | Census identities accept forms rejected by the matrix contract

`LedgerCliCensusAnnotation.__post_init__` checks only that the first character
of each segment is lowercase and that the segment becomes alphanumeric after
underscores are removed. It accepts `ledger.fooBar` and Unicode alphanumeric
segments, while the owning `LedgerCapabilityMatrixV1` contract permits only
ASCII `[a-z][a-z0-9_]*` segments. Current annotations happen to conform, but a
future invalid identity can pass the census and fail only during later matrix
admission rather than at its owning declaration boundary.

### reference-overloaded-count | medium | The reference says eight overloaded endpoints although the census has ten

The reference describes 45 supplemental sub-operations “across eight
overloaded endpoints.” The live annotation tuple has ten such endpoints:
classify, evidence pull, export, history, import, list, remove, reset, rule
apply, and split. The total of 45 and the source SHA-256 are accurate, but the
endpoint-family count and therefore the evidence narrative do not align with
the production projection.

## Recommendations

1. Add census-owned positive and mutation tests to the existing
   `test_command_specs.py` suite. The tests must consume the live graph and
   demonstrate detection of new/missing/unknown/duplicate endpoint
   adjudications, duplicate sub-operation identities, invalid stable
   identities, and unavailable handler/schema declarations without mutating
   the contributor worktree.
2. Rewalk every branch of each overloaded handler, add the missing bulk CSV
   classification identity, and decide explicitly whether auto-split
   preview/apply/reject outcomes require separate identities under the same
   behavior-distinct rule used for model classification.
3. Format the production source, rerun lint, format, type, focused tests, and
   the new detector suite, then refresh the evidence digest.
4. Use the same lowercase ASCII dotted-identity validator as the campaign
   matrix contract rather than maintaining a weaker private approximation.
5. Correct the reference's overloaded-endpoint count and any totals changed by
   the renewed sub-operation census before requesting another independent
   S04 review.
