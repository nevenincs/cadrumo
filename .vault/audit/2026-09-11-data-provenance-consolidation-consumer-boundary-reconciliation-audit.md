---
tags:
  - '#audit'
  - '#data-provenance-consolidation'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:5cf6eebace7a16eda4ff6d0cd7191287299446af4f643cf62bebf7d88accf0ec'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# `data-provenance-consolidation` audit: `consumer boundary reconciliation`

## Scope

Reconciled the accepted `compile artifact identity and role; preserve specialized authority` ADR, its plan, grounding research and lane-map reference, W04 execution and review records, and the live catalog, registry compiler, authority publisher, synchronizer, and their real-path tests.

Decision inventory: the accepted ADR is the sole decision home for a typed read-only catalog that is caller-bounded rather than a replacement filing authority. The research records the evidence for that boundary; the plan schedules its rollout; W04 records and tests supply execution evidence. The catalog compiler has no filesystem traversal and receives `known_paths` from its caller. The registry compiler supplies its cited record-design sources, and the synchronizer supplies its payload walk. Registry validation calls the registry compiler projection before source-byte verification, while `publish_authority_candidate_workflow` invokes the development publisher's complete candidate-validation path.

## Findings

### consumer-boundary | low | Accepted caller-boundary decision agrees with the live implementation

`compile_artifact_catalogue` is a pure compilation result over caller-provided paths. `compile_record_design_manifest_catalogue` narrows registry input to cited record-design sources and verifies those sources' exact identities against independently acquired manifest identities. The synchronizer supplies its own payload boundary and receives typed diagnostics. Neither path scans all bundled configuration or exposes raw catalog records to filing runtime; runtime authority remains the published, validated authority artifact.

### s23-real-boundaries | low | The two real consumer-owned S23 assertions cover the intended paths

The synchronizer's shipped-data test asserts that its payload candidates equal catalogued roles plus precisely the named M200 debt, with no overlapping roles and no diagnostic other than that debt. The registry companion test loads the committed registry, compiles the record-design manifest projection from the actual source mapping, requires empty diagnostics and equality between cited paths, roles, and identities, then runs the production identity-binding verifier. The two focused suites passed in the reconciliation run.

### s24-collection | high | The real publisher workflow assertion cannot currently collect

The S24 test correctly stages a minimal registry and record-design manifest, mutates the manifest digest, invokes `publish_authority_candidate_workflow`, and proves that a prior authority artifact remains byte-for-byte unchanged after refusal. It currently stops during collection because `dev.registry.tests._referential_integrity_support` uses a relative import beyond the top-level package. This is a concurrent registry-test-support relocation defect, not a catalog or publisher workaround; no S24 passing result exists until that import is repaired and the real workflow test runs.

### lifecycle-wording | medium | The plan headline retains broad bundled-data wording after the caller-boundary clarification

The ADR's implementation and consequences now unambiguously say the catalog is caller-bounded and not a universal configuration inventory. S23 has the same concrete scope. The plan title sentence still says it will compile a catalog for bundled `_data`, and its W04 phase introduction still says it proves the shipped tree. Those phrases can be read as the rejected global taxonomy. The detailed W04 steps and verification paragraph are aligned, so this is documentation ambiguity rather than code-versus-ADR drift.

### lifecycle-records | low | S23's rolling review retains superseded recommendations beside its resolved finding

The S23 review records the original high finding that the registry boundary lacked a real-path assertion, followed by a resolved-finding entry documenting the added companion test. Its recommendation still says to add that assertion. The audit history is useful, but the unqualified recommendation is stale and can mislead an executor; it should be marked fulfilled or removed by its owner.

### mechanical-baseline | low | S08 and S09 empty-record warnings are separate historical hygiene debt

The feature-wide vault check reports empty `Changes` sections for the S08 and S09 execution records and empty `Scope`, `Findings`, and `Recommendations` sections for their review audits. They predate this reconciliation and do not contradict the consumer-boundary decision, S23 evidence, or S24 target. They remain separate documentation hygiene work and were not edited here.

## Recommendations

- Repair the relative import in the concurrent registry test-support relocation, then run the real S24 publisher-workflow test and capture its execution and review evidence. Do not replace it with a direct compiler/unit assertion.
- Amend the plan's broad headline and W04 introductory phrase to name "each production consumer-owned evidence boundary," matching the accepted ADR and already-completed S23 scope. This is a wording alignment, not a new architectural decision.
- Have the S23 review owner mark the original registry-boundary recommendation fulfilled, retaining the historical finding and its resolution.
- Complete S26 only by running its distinct sidecar, export reproduction, normative-text authenticity, and calculation-oracle owner gates after the registry relocation is green; record any unrelated baseline failures separately.
- Repair the pre-existing S08/S09 execution and review record bodies in their own scoped documentation task.
