---
tags:
  - '#audit'
  - '#registry-declaration-hardening'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:df4ff6202e07bb99ca5a0f01b57a7a7f3b8d9fd3410e0202bfeaa0d6b9d5f16e'
related: []
---
# `registry-declaration-hardening` audit: `modelo 200 publication review`

## Scope

Reviewed the live Modelo 200 generated-tree operator path against `W04.P07.S75`, the accepted generator authority, the proposed operator invocation decision, and the registry publication, filing-grade, source-binding, CLI, quality-gate, and shared-worktree rules. The review covered bootstrap assembly, generated-tree validation and publication, semantic-map normalization and join behavior, and focused tests. No production code was changed.

## Findings

### bootstrap-transport-authority | high | absent-tree transport is synthesized rather than source-bound

`_prepare` enables bootstrap for every selected revision whose target `export` directory is absent, then constructs `GeneratedExportBootstrapTransport` with a layout id derived from the modelo/revision spelling and an unconditional `crlf` line ending. The transport value carries neither the selected `source_ref` nor its SHA-256, and `revision_render_inputs` validates only the generated layout-id spelling; it accepts the caller's line ending without proving it against an official design or reviewed source-bound declaration. Thus the semantic map and render profile remain source-pinned while transport does not: a missing tree can acquire guessed transport merely from filesystem absence. This contradicts the accepted generator decision's refusal of implicit defaults and guessed output and is broader than the exact owed Modelo 200 enrolments.

### check-publish-state-binding | high | publish can operate on a different live state than the state that passed check

The `publish` branch of `_run` checks one prepared invocation, discards it, calls `_prepare` again from the live bundled registry, and publishes the second candidate. No source/map/profile digest or target absence/tree digest from the check is carried into the publisher, and the transactional lock is acquired only inside publication after this split. In the explicitly shared worktree, registry authorities or the target tree can change between the two preparations; the second candidate can then validate and replace the target even though that candidate was never compared by `check_generated_export_tree` to that live target. This violates the proposed operator decision that publish additionally refuses when check would not pass and makes the preflight result non-authoritative under concurrent edits.

### filing-refusal-regression-proof | medium | the safety test does not prove filing refusal after bootstrap publication

The current tests prove synthetic absent-tree publication and separately prove that the untouched bundled Modelo 200 authority refuses a filing-grade snapshot. They do not publish a generated Modelo 200 tree into an isolated copy of its real revision, reload that post-publication registry through `ValidatedRegistryAuthority`, and prove that calculation-grade selection succeeds while filing-grade selection still refuses. The implementation currently leaves `authority_grade` outside the published export tree, but the named safety condition lacks an end-to-end detector with teeth across the actual bootstrap cutover.

### bootstrap-transport-authority-rereview | high | source identity is pinned but the bootstrap transport value is still guessed

Re-review confirms a partial fix: `GeneratedExportBootstrapTransport` now carries `source_ref` and `source_sha256`, `revision_render_inputs` compares both with the selected catalogue source, and the parsed intermediate must retain the same digest. The authority gap remains because `_prepare` still creates the transport for every absent `export` directory with an unconditional `crlf` line ending and a layout id synthesized from modelo/revision spelling. Binding a caller-created default to a real source digest proves association, not that the source or a reviewed transport declaration supplied the value. No exact-target enrolment or negative line-ending authority test limits the widening. The original HIGH remains open.

### check-publish-state-binding-rereview | high | candidate reuse does not bind the live target checked before cutover

Re-review confirms that `_run` now carries the same prepared candidate and `RenderedExportTree` from `_check` into `_publish`, closing the authored-input drift caused by a second `_prepare`. The checked target state is still discarded: `CheckedGeneratedExportTree` retains the published manifest, but `_check` returns only the result token and rendered candidate, and publication receives no expected target absence or target manifest/tree digest. Another writer can create or replace the target after check and before the publication lock; the publisher then treats that newer tree as the rollback target and replaces it without proving it is the tree that passed check. The original HIGH remains open under the shared-worktree concurrency contract.

### check-publish-state-binding-final | high | the expected target is sampled after check and covers only the manifest file

Final re-review finds that the under-lock assertion does not yet carry the state established by `_check`. `_publish` recomputes `target_absent` and `target_digest` immediately before calling the publisher, after the read-only check has returned. A target created or replaced in that interval is therefore accepted as the new expected state instead of refused. For an existing target, the receipt hashes only `_generation.provenance.json`; a concurrent change to another generated member with the manifest left unchanged also passes `_require_expected_target_state`. The assertion is correctly placed under the exclusive lock, but its expected value is neither check-minted nor a complete tree/package identity. The target-state HIGH remains open.

### bootstrap-target-detector | medium | exact enrolment has no focused mutation gate

The reviewed bootstrap TOML and `_bootstrap_target` now close the transport-authority code defect: only the exact Modelo 200 2025 target, source reference, and source SHA-256 are enrolled, and the reviewed row supplies the layout identity and line ending. No focused test mutates the enrolment source digest, line ending, duplicate row, or target identity and proves refusal through the CLI boundary. The implementation refused an unenrolled target in a direct fast probe, but the quality gate still lacks durable detector teeth for this authority file.

### check-time-receipt-closure | high | existing-target receipt is observed after the check completes

The typed receipt now carries the manifest digest plus every regular generated output digest, and `_require_expected_target_state` compares that complete identity under the exclusive publication lock. The three focused mutation detectors pass. The existing-target branch still calls `GeneratedExportTreeTargetStateReceipt.observe` only after `check_generated_export_tree` has returned. A concurrent replacement between the successful target comparison and that observation is minted into the receipt as the expected state and then passes the under-lock check even though it was never checked against the candidate. The target-state HIGH remains open until the receipt is created from the exact bytes checked by `check_generated_export_tree`, or an observation made before check is proved unchanged both after check and under lock.
## Recommendations

- For `bootstrap-transport-authority`, make absent-tree transport an explicit reviewed declaration bound to the exact official `source_ref` and SHA-256, and enroll only exact owed targets. Refuse missing or mismatched transport authority. Add negative tests for changed source hash, wrong line ending, wrong layout id, and an unenrolled absent tree.
- For `check-publish-state-binding`, publish the same immutable prepared candidate that passed check, or mint a check receipt containing every authored-input digest plus the target absence/tree digest and verify it while holding the publication lock. Add a mutation test that changes an authored input or target between check and cutover and requires refusal.
- For `filing-refusal-regression-proof`, add an isolated real-Modelo-200 post-publication authority test that asserts the generated layout loads and exports while the revision remains calculation-grade and a filing-grade snapshot still refuses.
- Re-review update: retain the source-ref and source-digest checks, but move `line_ending` and any non-derived layout identity into an explicit source-bound reviewed bootstrap declaration. Do not infer enrolment from directory absence.
- Re-review update: carry the checked target absence or exact manifest/tree digest into `GeneratedExportTreePublicationContext` and compare it under the exclusive lock before candidate validation or cutover.
- Final re-review update: return a typed target-state receipt from `_check`, including exact absence or a complete regular-tree/package identity, pass that receipt unchanged into `_publish`, and verify it under the lock. Add mutations both for target appearance and for a non-manifest member changing with the manifest unchanged.
- Final re-review update: retain the exact reviewed bootstrap row and add focused CLI-boundary mutation tests for every enrolled identity and transport field.

## Final re-review status

- `bootstrap-transport-authority`: resolved in code by the exact, source-hash-bound reviewed target enrolment; the missing mutation gate is tracked separately at MEDIUM.
- `check-publish-state-binding`: open at HIGH because the expected target is sampled after check and does not cover the complete target tree.
- `filing-refusal-regression-proof`: remains open at MEDIUM.
## Closure re-review status

- `bootstrap-transport-authority`: resolved; the new unenrolled-source mutation detector passes.
- `check-publish-state-binding`: remains open at HIGH because the existing-target receipt is observed after check rather than minted from the checked bytes.
- Full-tree under-lock comparison and all three focused mutation detectors pass.
## Receipt-order closure status

- `check-publish-state-binding`: resolved. `_check` observes the complete target receipt before validation/comparison, returns that exact receipt, and `_publish` carries it unchanged to the under-lock full-tree assertion.
- Scoped closure verdict: no HIGH or CRITICAL finding remains.
