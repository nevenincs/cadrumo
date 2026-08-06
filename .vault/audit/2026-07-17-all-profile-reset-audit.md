---
tags:
  - '#audit'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:9b0e63dc95c5e326ef147844022247ded8dde2e5ab8ef94aadccd2a0be9e278d'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
  - "[[2026-07-17-all-profile-reset-adr]]"
  - "[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]"
---

# `all-profile-reset` audit: `all-profile reset safety closure review`

## Scope

Independent, fresh-context safety review of the all-profile-reset P01 through P03 closure — the original safety-critical work of this successor, which existed to close the dangling-pointer and retention-bypass defect where reset could delete the active bucket leaving a dangling pointer and could bypass the retention floor, both silently. The review examined the reset orchestration in `config_reset.py` and its journal, the pointer and delete ordering, retention enforcement, target scoping, single-writer delegation, and lock reentrancy.

**Verdict: PASS CLEAN.** No Critical, High, Medium, or Low findings. The safety closure is independently verified sound.

## Findings

### crash-safety-all-boundaries | confirmed | Crash-safe at all 11 phase boundaries with roll-forward semantics

The reset is crash-safe at all eleven phase boundaries. A fresh-process `os._exit` roll-forward recovers every window including the hard `_after_effect` windows, and recovery rolls forward rather than rolling back, so a partially-applied reset completes deterministically rather than reverting to an inconsistent mid-state.

### dangling-pointer-closed | confirmed | Pointer cleared before delete with an active-bucket-delete refusal backstop

The dangling-pointer defect is closed: the active-bucket pointer is cleared before the bucket delete, and an active-bucket-delete refusal serves as a backstop so no path can delete a bucket that a live pointer still references.

### retention-independently-enforced | confirmed | Retention floor re-enforced at the writer, not only the orchestrator

The retention floor is independently re-enforced at the writer (`_enforce_retention_floor`), not only through an orchestrator override, backed by a preflight pause and a post-assessment fingerprint recheck. The floor cannot be bypassed by reaching the writer through a path that skips the orchestrator override.

### target-scoping-byte-verified | confirmed | Reset is target-scoped, proven byte-identical for unrelated data

Target scoping is byte-verified: a reset of one target leaves unrelated buckets and session files byte-identical, so the destructive operation cannot reach beyond its declared target.

### single-writer-delegation | confirmed | Reset composes the single-writer primitives with no parallel write path

Reset delegates its writes to the existing single-writer primitives and introduces no parallel write path, preserving their atomicity and lifecycle-event emission.

### lock-reentrancy-sound | confirmed | Lock reentrancy actively hunted and proven deadlock-free

Lock reentrancy was actively hunted for deadlock and proven sound: reentrant acquisition uses depth counters so a nested acquire of a held lock does not self-deadlock.

### test-integrity-real-crash-resume | confirmed | 37 real crash-resume tests, no doubles

The 37 tests exercise real crash-resume behaviour with fresh-process re-entry, carrying no mock, skip, or xfail.

## Recommendations

No action required. The P01 through P03 safety closure is independently verified clean and belongs on the campaign-close honesty trail as an externally-confirmed pass of the original dangling-pointer and retention-bypass defect.

## Campaign-close honesty review (2026-07-19, fresh-context)

Fresh-context review run against the 31/31 closure claim at HEAD, per the
campaign-close honesty-review gate. The reviewer re-ran the safety suites
independently rather than trusting exec-record pass counts.

### s31-bookkeeping-race | resolved-at-head | S31 box and exec record landed concurrently with the review read

The sole MEDIUM finding — `P05.S31` unchecked with no exec record — was a
read-vs-landing race: commit `515a474acc` (enrolment box + retroactive exec
record citing the atomic `00c3ab005d` landing) was committed while the review
was in flight. Verified checked with record at HEAD. The underlying MCP
identity-gate sweep itself was independently confirmed done: no
`config.profile.sandbox.use` reference anywhere in `src/cadrumo`, MCP suite
green.

### coverage-report-staleness | resolved-at-head | S29 deferral closed by `0342e4b890`

The S29 exec record's deferred terminology coverage-report staleness was
regenerated at `0342e4b890`; zero `sandbox use` / `config rekey` rows remain.

### safety-claims-reproduced | confirmed | Reviewer re-ran every safety suite

Crash-resume, concurrency, retention-floor, fingerprint-guarded deletion, and
grammar-invariant suites re-run green (30 + 75 focused tests); implementation
read in full — sorted-tuple lock order, retention persisted before mutation,
deleting-ownership marker persisted before delete, resume re-assesses
fingerprints and pauses on drift. No mocks, monkeypatch, skip, or xfail in any
safety test file.

### Verdict

STRUCTURALLY COMPLETE at 31/31. Every plan §Verification requirement holds at
HEAD with independently-reproduced evidence; this section is the required
fresh-context honesty pass on the closure trail.
