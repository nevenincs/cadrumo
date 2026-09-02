---
tags:
  - '#audit'
  - '#registry-declaration-hardening'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:e2296a1042347a83a7a354635e71b305589b4caf874306844201adc280b2ddae'
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

## Recommendations

- For `bootstrap-transport-authority`, make absent-tree transport an explicit reviewed declaration bound to the exact official `source_ref` and SHA-256, and enroll only exact owed targets. Refuse missing or mismatched transport authority. Add negative tests for changed source hash, wrong line ending, wrong layout id, and an unenrolled absent tree.
- For `check-publish-state-binding`, publish the same immutable prepared candidate that passed check, or mint a check receipt containing every authored-input digest plus the target absence/tree digest and verify it while holding the publication lock. Add a mutation test that changes an authored input or target between check and cutover and requires refusal.
- For `filing-refusal-regression-proof`, add an isolated real-Modelo-200 post-publication authority test that asserts the generated layout loads and exports while the revision remains calculation-grade and a filing-grade snapshot still refuses.
