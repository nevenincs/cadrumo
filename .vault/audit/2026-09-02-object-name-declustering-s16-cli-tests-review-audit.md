---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:5af0fea0897d4a13514b453f372acbc81d9f319907707ba16dd36708832a18f0'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s16 cli tests review`

## Scope

Reviewed the S16 CLI detector-teeth suite against the accepted object-name declustering ADR,
research, reference, and plan and the current CLI, manifest, graph, rehearsal, and replay
contracts. The review covered modes and arguments, strict structured input adapters,
deterministic output, default non-mutating rehearsal, explicit receipt-bound apply,
inventory/plan/verify behavior, canonical component selection, and expected versus
programming-error exit semantics. No production or test code was modified.

## Findings

### generated-context-coverage | high | The untested CLI graph adapter rejects valid generator-backed manifests

Every CLI context fixture is definition-only. Production `_context` passes only repository
import edges to `build_manifest_components`; unlike rehearsal, it derives no
`generated-artifact` edges from reviewed manifest commands and paths. The graph contract
therefore observes no generated class and refuses a valid generator-backed manifest before
plan, rehearsal, or apply. The missing end-to-end generator CLI case allows an accepted
workflow to remain unreachable while the suite is green.

### canonical-component-count | medium | Multiple-component refusal has no detector tooth

The real plan test exercises one valid component, while dispatch tests replace `_context`.
No manifest with two independent components proves that plan, rehearse, and apply refuse the
same non-canonical scope before either execution primitive is called. Removing or weakening
the exactly-one-component check would not fail the current suite.

### structured-result-adapters | medium | Rehearse and apply output tests assert only their mode labels

Dispatch tests return typed stub objects but inspect only `payload["mode"]`; the real
rehearsal immutability test likewise does not validate its JSON receipt. They do not assert
the exact serialized receipt/result keys and values or run a real CLI apply. Output adapters
could omit evidence, misbind result fields, or pass incorrect context arguments to replay
without these tests failing, despite structured output being the operator handoff.

### clean-verify-exit | medium | Verify exit semantics cover findings but not a clean inventory

The suite proves verify returns one when enforced findings remain and inventory remains
informational with findings. It never verifies a clean repository returns zero with a
zero-finding structured payload. A reversed or hard-coded nonzero clean branch would pass.

## Recommendations

Make CLI context construction use the same independently derived generated-edge authority as
rehearsal, then drive plan and rehearsal through a real generator-backed manifest. Add a
two-independent-operation manifest and assert all context-owning modes refuse before
rehearsal or replay. Assert exact JSON envelopes for plan, rehearsal, and apply, including
all receipt/result evidence, and perform one real receipt-bound CLI apply that verifies live
bytes. Add a clean verify case asserting exit zero, stdout-only deterministic JSON, and zero
enforced findings.

Preserve the suite's existing strong coverage: safe manifest and receipt paths, strict receipt
schema and digest validation, apply-only receipt arguments and explicit identity, default
rehearsal with unchanged live bytes, manifest-independent inventory and verify, malformed
manifest refusal, deterministic JSON and human output, link-like root refusal, expected
stderr/exit-two mapping, and unexpected programming-defect traceback behavior.

## Validation

The focused suite passed 35 tests in 14.18 seconds. Ruff, Ruff-format, and ty checks passed.
Final review status is one high and three medium findings, with no critical or low findings.

## Re-review status

Resolved: `generated-context-coverage` is closed by moving canonical component derivation into
the shared `canonical_object_name_component_set` authority used by both CLI context and
rehearsal. The new generator-backed CLI case loads a real manifest, produces the exact plan
component envelope, executes real disposable rehearsal, asserts the exact receipt envelope
and owner command outcome, and proves live bytes remain unchanged.

Resolved: `canonical-component-count` now builds a real manifest containing two independent
operations and declarations. Plan mode returns exit two with empty stdout and the exact
two-component refusal before either mutation mode can run.

Resolved: `structured-result-adapters` now asserts complete plan and rehearsal envelopes
against serialized typed objects and runs the real replay implementation through CLI apply.
The apply case verifies exact `ObjectNameReplayResult` serialization and the expected live
symbol mutation, so omitted fields or incorrect replay dispatch no longer pass.

Resolved: `clean-verify-exit` now runs verify against a clean source inventory and asserts
exit zero, the verify mode envelope, and zero enforced findings.

The four targeted closure cases passed in 7.09 seconds. The reported full focused suite
passed 39 tests. Ruff, Ruff-format, and ty checks passed for CLI, shared rehearsal authority,
and the CLI tests. Final S16 status is no open critical, high, medium, or low findings.
