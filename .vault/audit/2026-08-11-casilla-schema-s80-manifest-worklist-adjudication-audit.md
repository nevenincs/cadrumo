---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b38e59d51e0cfeb8bb623a0826253732e7ced5d078d6fce37dc702b812a9c1dd'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# `casilla-schema` audit: `S80 manifest worklist adjudication`

## Scope

Formal read-only review of `W05.P11.S80` against the governing casilla-schema plan, accepted completeness decisions and research, the historical `W01.P02.S08` execution record, the S80 execution record, the production completeness predicate and manifest schema, and the two cited focused tests. The review independently recomputed the loaded validated registry population through `bundled_authority()` and `calculation_closure_casilla_ids`, inspected commit `a3c07ef209` for the S80/S81 plan mutation, and preserved all unrelated CLI ledger and export worktree changes.

The independent result is `manifest_absent=38`, `zero_closure=38`, and `missing_required_manifest=0`. The production contract agrees: a missing manifest is valid exactly when canonical calculation closure is empty, while the manifest schema rejects an empty placeholder. S80 authored no registry rows and correctly identifies S08's worklist predicate as false-positive rather than treating manifest absence alone as a data gap. Both cited focused tests pass against the real repository registry.

## Findings

### plan-sequencing | high | S81 is ordered after the false-positive authoring rows it must retire

The plan's binding entry protocol says each session starts from the next open step. `W01.P02.S42` through `S79` remain open in an earlier wave and phase, while the corrective `W05.P11.S81` is later in document order and S80 is also left open. Consequently the plan still directs a conforming next session into Modelo 121 manifest authoring before it can reach the cleanup that proves such authoring would fabricate calculation closure. S81's listed cleanup actions are substantively sufficient, but its placement and current open-state sequencing do not make that scope executable before the unsafe rows it retires.

### rag-evidence-record | medium | S80 records a code semantic search as successful when it was blocked

The S80 Notes say both code and vault semantic searches succeeded and that no metadata-job outage blocked the step. Session evidence instead shows the vault RAG search succeeded, while code RAG was blocked by active metadata job `c85efeb1`; exact whole-file reads, targeted `rg`, and runtime probing were used as the fallback. Those fallbacks provide adequate implementation evidence for this adjudication, but the immutable execution record must report the actual discovery boundary rather than claim a semantic-search success that did not occur.

### exact-count-gate | medium | The fleet test violates the prohibition on exact-count pass conditions

`test_calculation_completeness_gate_is_live_for_every_calculation_bearing_modelo` correctly checks the load-bearing property for every loaded revision: non-empty closure requires a manifest and empty closure forbids one. Its final `assert dormant == 38`, however, makes a hand-maintained corpus tally an additional pass condition. The always-on quality rule explicitly forbids exact counts as pass conditions and requires gating on the property instead. The adjacent enumerated comment has the same maintenance smell. The second focused test is a sound real-schema validation of the legitimate zero-closure case, and neither focused test uses fakes, mocks, stubs, skips, or monkeypatches.

## Recommendations

- Re-sequence the correction so the plan cannot select any of `W01.P02.S42` through `S79` before their retirement. Preserve immutable step history, but make the corrective lifecycle action the effective next executable step using the plan CLI and verify the resulting `vaultspec-core status casilla-schema` output before accepting S80.
- Correct the S80 execution record to state that vault RAG succeeded, code RAG was blocked by metadata job `c85efeb1`, and whole-file, targeted-search, and runtime evidence supplied the fallback. Remove the contrary no-outage assertion.
- Extend S81 to remove the exact `dormant == 38` pass condition and the hand-maintained dormant-id inventory while retaining the per-revision bidirectional property assertions. Record `38/38/0` as execution evidence, not as a permanent test invariant.
- After those corrections, rerun the two focused tests, independently remeasure the validated authority partition, and run the plan/status and vault conformance checks named by S81.

## Verdict

**CHANGES REQUESTED.** The semantic adjudication, independent `38/38/0` measurement, fallback implementation evidence, and no-fabrication conclusion pass review. Acceptance is blocked by the plan sequencing hazard, the inaccurate RAG execution note, and the exact-count test-quality violation, none of which the current S81 wording and placement fully resolves.
## Re-review resolution

### plan-sequencing resolution

Resolved. `W01.P02.S42` through `S79` and the unexecuted `W05.P11.S81` are retired and absent from the live step rows, while their identifiers remain recorded in the CLI-maintained retired-id annotation. S80 now owns the cleanup. `vaultspec-core status casilla-schema` reports 42 live steps, 23 complete, and next open `W03.P07.S24`; no false-positive manifest-authoring row can be selected before the correction.

### rag-evidence-record resolution

Resolved. The S80 execution record now states the exact discovery boundary: vault RAG succeeded, code RAG was blocked by metadata job `c85efeb1`, and whole-file reads, targeted `rg`, and the public `bundled_authority` plus `calculation_closure_casilla_ids` runtime probe supplied the fallback. It also records that external commit `a3c07ef209` absorbed the initial S80/S81 lifecycle files with unrelated work and carries that non-atomic history forward without rewriting it.

### exact-count-gate resolution

Resolved. The fleet test no longer asserts `dormant == 38` and no longer embeds the hand-maintained dormant-revision inventory. It still loads the real committed registry tree and checks every revision bidirectionally: non-empty calculation closure requires a manifest and empty closure forbids one. Independent positive evidence remains for at least one calculation-bearing revision and at least one zero-closure revision. The focused zero-closure schema validation remains real and unchanged.

## Re-review verification

- The two focused tests passed: `2 passed in 12.75s`.
- Focused Ruff passed for `test_record_design_completeness.py`.
- Plan status reports 42 live steps, 23 complete, and next open `W03.P07.S24`.
- Feature-scoped modified-stamp and exec-mapping checks are clean.
- Feature-scoped body-sections reports only the pre-existing out-of-scope empty Description warning in the S02 execution record.
- Scoped `git diff --check` passed for the S80 repair files.
- No registry data or production code was added, and this review modified only this audit through the VaultSpec CLI.
- Delivery integrity is recorded without history rewriting: `3dfbd2b036` externally absorbed the initial audit, `cfb57c1325` absorbed the lifecycle retirements and document corrections, and `efeb24cb7a` absorbed the exact-count test repair, each with unrelated work; the final bounded closure retains only the execution correction, audit resolution, and checked plan state.

## Final verdict

**PASS.** All three review findings are resolved. The corrected lifecycle no longer exposes false-positive authoring work, the execution record accurately preserves the discovery and external-history boundary, and the real-registry property test complies with the no-exact-count rule.
