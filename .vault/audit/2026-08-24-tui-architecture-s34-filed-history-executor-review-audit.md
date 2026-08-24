---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:10579769313f0a105e6410de3fc9aa6ca1b7eda424080ae7f438860c3b64615f'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-W03-P07-S34]]"
---

# `tui-architecture` audit: `S34 filed-history executor review`

## Scope

Formal review of `W03.P07.S34` against the accepted recorded filed-history
operation decision, its research grounding, plan row, execution record, the
canonical `pull_filed_history` composition, and the sync-run provenance port.
The review covered delegation, active-subject binding, definition capabilities,
effect classification, result-reference ownership, package boundaries, and the
real supervisor test composition.

The executor is otherwise a thin application boundary. It validates the active
profile subject, publishes only supervisor-owned phase/effect facts, and forwards
the immutable request and injected application persistence port to the canonical
composition. It adds no discovery, register, capture, persistence, wallet,
notification, or sync-run writer. The definition truthfully declares `RECORDED`,
idempotent submission, unsupported cancellation, absent deadline, interrupt on
owner loss, definition-subject exclusion, no owned resource, detach, no
interaction, and the complete current effect set.

## Findings

### s34-result-authority | high | The executor returns a synthetic operation token instead of a domain-owned result reference

`FiledHistoryOperationExecutor.execute` receives the typed
`FiledHistoryOnboardingRun`, uses it only for effect classification, discards it,
and returns `filed-history:{operation_id}`. The executor protocol permits only an
optional domain-owned result reference; the operation ID is generic lifecycle
identity and does not resolve the onboarding result, captured evidence, wallet
decision, notification snapshot, or child `SyncRunRecord`. This also leaves the
definition's `FiledHistoryOnboardingRun` result schema without an authoritative
record behind the returned reference. A frontend can therefore observe that the
executor reached settlement but cannot retrieve the typed result it declares.

The execution record correctly discloses that the canonical onboarding result
does not expose the identity returned by `record_sync_run`. That is a real S38
authority prerequisite, not merely missing test coverage: the child provenance
identity must become observable through the canonical writer/result boundary.
However, assigning its proof to S38 does not make a fabricated operation-scoped
token domain-owned, so S34 cannot close while it returns that token.

## Recommendations

Extend the canonical filed-history result/provenance boundary so the existing
writer exposes a stable domain reference without duplicating `record_sync_run`.
Have the executor return that resolvable domain-owned reference and retain the
typed onboarding result behind the definition's declared schema. S38 should then
prove the child provenance join and terminal projection; it must not reconstruct
the identity or introduce a second writer.

The focused executor suite passes two integration tests using the production
supervisor, encrypted secure-reference repository, filesystem journal and lease,
real sync-run repository, and canonical `pull_filed_history` composition with a
local discovery boundary. It contains no mock, fake, patch, skip, or xfail. Ruff
lint, Ruff format, focused BasedPyright, scoped diff integrity, the facade export
scan, and the targeted private-import search are clean.

Close verdict: REVISION REQUIRED. One High result-authority finding remains.

## Remediation re-review

### s34-result-authority | resolved | The canonical encrypted sync-run reference now crosses the executor boundary unchanged

`record_sync_run` remains the sole filed-history provenance writer and now
returns the same persisted record it always created. The canonical
`sync_run_record_key` converts that record's declared surface and bucket-event
identity into the typed `SyncRunRecordReference`; the bulk capture retains it,
`pull_filed_history` copies it unchanged into `FiledHistoryOnboardingRun`, and
`FiledHistoryOperationExecutor.execute` returns that value directly. The prior
synthetic `filed-history:{operation_id}` token is absent, and neither the
executor nor the onboarding composition reconstructs or repeats the write.

The real encrypted `SyncRunRecordRepository` proof loads the returned key and
confirms that its extracted canonical identifier is identical and its bucket is
the active subject. S38 therefore retains the narrower acceptance responsibility
to prove the supervisor terminal child-provenance join; it no longer owns a
missing-authority repair. This resolves the High finding.

## Re-review gates

Ruff lint, Ruff format, focused BasedPyright, and scoped diff integrity pass for
all remediated files. The three focused integration tests currently fail before
entering any S34 code because shared-worktree profile enrollment now refuses in
`isolated_runtime_profile` with `profile enrollment publication requires a
recovery envelope`. The same two S34 cases passed immediately before that
concurrent custody-boundary change, and all three present failures share that
unrelated fixture setup stack. This is recorded as external concurrent gate
interference rather than an S34 finding; the coordinating session must rerun the
focused file after the custody step settles.

Close verdict: PASS for S34 implementation and architecture. The prior High is
resolved; final green integration attestation remains a coordinating-session
rerun because of unrelated shared-worktree custody WIP.

## Final closure evidence

The shared profile fixture regression is reconciled through the canonical
production authority. `publish_test_profile_capsule` and the existing seeded
capsule path now call public `enroll_profile_recovery`, pass its real recovery
envelope into `ProfileCapsuleLifecycle.create`, and wipe the scoped recovery key
in `finally`. The helper still uses real custody material, profile sessions, and
capsule publication; it does not fake a recovery envelope, bypass the enrollment
guard, or introduce a filed-history-specific fixture route.

The focused filed-history executor lane now passes all three integration tests,
including exact encrypted resolution of the canonical sync-run reference. The
sync-run application lane passes all ten unit tests. Ruff lint, Ruff formatting,
focused BasedPyright, scoped diff integrity, and the complete facade export scan
all pass; the facade scan reports 5,172 modules, 259 facades, and zero syntax,
forward, or mirror breaks. No mock, fake, patch, skip, or xfail mechanism is used
by the S34 executor tests, and the canonical-home search finds no second
`save_with_bucket_event` implementation or filed-history `record_sync_run`
writer.

Final close verdict: PASS. S34 is fully closed; the prior concurrent-gate caveat
is superseded by the green regression evidence above, and no open finding
remains.
