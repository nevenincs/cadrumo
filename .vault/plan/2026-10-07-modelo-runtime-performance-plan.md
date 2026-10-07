---
tags:
  - '#plan'
  - '#modelo-runtime-performance'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]'
  - '[[2026-10-05-google-outbound-review-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:9db59962919622a7cbf9a1f97e616f55612977983f14d46205bbec2a6a655c3e'
---

# `modelo-runtime-performance` plan

## Description

Approved 2026-10-07

Authorization basis: the user requested a detailed explanation of the Modelo100 timeouts and explicitly directed production-capable optimization of degraded core loading and work that cannot complete. This plan covers measured shared bottlenecks on the real Modelo100 runtime startup, calculate and export path, with smaller Modelo controls. It is not limited to the previous static-quality task.

The previous canonical and isolated release-mask fixture runs exceeded the unchanged 300-second pytest setup limit while waiting for actual native runtime export. A bounded instrumented run also lost the runtime connection after durable calculation. Three release-mask assertions did not execute. Serializer-only timings do not establish complete catalogue load timing or the total root cause. Reproduce against the current shared tree before applying repairs; concurrent desktop/runtime work has advanced since that evidence.

The accepted application-owned operation contract governs S02 schema identity, model mutation refusal and all runtime authority boundaries. Indexed authority storage governs generation pins, public immutable successful caches and selective component reads. The immutable saved-revision contract governs S03 exact historic data and rendering; runtime manager authority governs worker lifetime and responsiveness. Routine pure deduplication and bounded work within these owners needs no new ADR. Do not introduce new persisted formats, public protocols, relaxed validation, widened timeouts, stale read windows, cross-operation private caches or new dependencies. If measurement requires a costly commitment outside those constraints, route it through decision coverage before implementation.

The baseline is current HEAD f0be8532f5 plus existing peer edits. Root owns the current canonical three-test baseline session54030 and shared native/runtime runs. RAG service is unavailable; its attempted startup found an uninstalled managed Qdrant backend. Use the existing stack and exact known ownership locators plus working semantic vault search; do not disrupt peer services.

## Steps

- [x] `S01` - Measure current real Modelo100 startup calculation and export and retain bounded phase and load profiling; `dev/ci/modelo_runtime_benchmark.py (new), justfile benchmark invocation, dev/docs/sequences runtime fixture benchmark seams and owning tests`.
- [x] `S02` - Reduce measured operation schema generation and graph snapshot work while preserving exact public fingerprints and live mutation refusal; `src/cadrumo/application/operations/registry_schema_validation.py, _model_contract.py, schema_identity.py, owning operation registry tests and src/cadrumo/entrypoints/tests/test_operation_registry_schema_parity.py`.
- [x] `S03` - Optimize measured calculation revision decode and read paths without stale authority or cross-load private caches; `src/cadrumo/adapters/persistence/profile/modelos_calculation.py and owning calculation revision, rendering, verification and readback consumers/tests`.
- [ ] `S04` - Prove real Modelo100 completion and core loading improvement with regression controls and all blocking quality gates; `dev/docs/tests/test_sequence_goldens.py real runtime fixtures, focused Modelo100/303/131 and currentness/custody tests, generated import enrollment, feature audit and ledger`.

## Parallelization

Use vaultspec-team for disjoint S01, S02 and S03 investigation/implementation. A profiling worker owns S01 developer benchmark code and copied diagnostic scripts; it reads production owners but does not alter them. A schema worker owns S02 operation schema helpers and their tests. A revision worker owns S03 calculation revision decode/read owner and direct tests, reporting any required edit outside ownership first. Begin with read-only measurements and proposed mechanisms; implement only optimizations supported by measured current-path cost. Preserve all peer edits. Root owns plan/ledger/audit writes, shared metadata, Git staging/commits, native baseline and final production-route runs, and integrated review. Shared expensive fixtures are serialized; scoped pure tests may run independently. S04 follows final source repairs.

## Verification

Record before/after wall time and CPU for startup, operation registry compilation, calculation, encrypted catalogue decode/readback, export preparation and completion; use only safe synthetic metrics, never payloads or secrets. Separate cold and warm behavior and report call counts and retained/RSS evidence where meaningful. The real canonical three Modelo100 release-mask tests must complete and pass with the existing 300-second policy and native worker ownership. Do not replace them with doubles or remove gates. Require a measured reduction in the identified dominant core work, not merely a test timeout disappearance or a warmed global cache.

Use direct regressions to preserve schema graph/config/metadata/core-rebuild mutation refusals, identical public schema/definition fingerprints, exact saved bytes/digests, missing/stale/foreign parent/profile refusal, encrypted catalogue tamper rejection, evidence coverage and actual currentness at write boundaries. Check representative Modelo303 and Modelo131 boundaries as controls. Keep active-generation and post-write freshness checks intact. Require focused lint/format and all applicable configured type checkers before a Step closes, all twelve blocking code-quality gates after final source/enrollment, feature health and final integrated review. Every Step logs actual evidence and commits its owned change.
