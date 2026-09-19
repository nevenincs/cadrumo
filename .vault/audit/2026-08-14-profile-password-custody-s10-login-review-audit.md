---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b3d8c35d1a9ae9bc31f19f25271a4ad43805fe8c34dc71a6f639f72dd3b729c7'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` audit: `S10 candidate login handover review`

## Scope

Independent review of `W02.P04.S10` against the accepted custody roll-up and
the completed lifecycle/discovery phase. The review covered target resolution,
throttle ordering, current envelope and sentinel authentication, unbound B
candidate ownership, pointer compare-and-swap, live and record-session binding,
optional persisted acceleration, A retirement, rollback, crash behavior, real
six-case tests, negative legacy searches, and scoped static analysis. S11 and
production remediation were excluded.

## Findings

The candidate boundary is otherwise coherent. Target resolution and throttle
evaluation precede password resolution and Argon2. Current password material
loads the exact committed envelope and sentinel without recovery, manifest,
provider, or shared-master fallback. Cached B can resume only when the captured
pointer already selects B and the live binding does not disagree. Wrong or
malformed B closes only candidate material and leaves A's exact pointer, live
session, record session, and persisted B absence unchanged. Pointer publication
is captured-byte compare-and-swap; bind or acceleration failure restores A,
removes B acceleration, closes B, and compare-and-restores the pointer.
Unavailable keyring acceleration is explicitly process-scoped rather than an
authentication failure.

The original activation-order HIGH is closed. `_record_activation` now executes
inside the rollback-protected promotion transaction, before A retirement, and
uses the journal's stable UTC instant. The content-addressed bucket event makes
replay idempotent. A real corrupt-B event-store test proves exact A pointer,
live-session, record-session and persisted-session preservation while B's
candidate and acceleration are removed. The five real subprocess cases kill
the process at pointer-published, B-bound, accelerated, activated and A-retired
receipts and recover deterministically to authenticated B without test doubles.

### s10-handover-phase-publication-is-idempotent | resolved | Same-phase durable receipt converges safely

The semantic filesystem CAS finding is closed. The custody adapter now owns
compare-and-replace and compare-and-clear as single anchored operations. POSIX
uses exchange/no-replace primitives and verifies the displaced inode bytes;
Windows uses `ReplaceFileW` with a verified backup or a no-delete-shared leaf
handle. A mismatching canonical substitute is restored or preserved, and the
application no longer composes read-then-write/unlink. The new sibling-process
test substitutes after CAS staging and proves refusal without losing the
substitute.

The final idempotence gap is closed. One custody operation now accepts an
already-current receipt as a no-op, otherwise transitions only from absence or
the exact predecessor, and preserves every mismatch. POSIX and Windows retain
the verified predecessor in one deterministic sidecar until same-receipt
cleanup succeeds, so an ambiguous post-publication cleanup failure converges on
retry. Terminal clear reconciles that sidecar before atomically removing only
the exact receipt.

Real tests cover duplicate `PREPARED`, duplicate later-phase publication,
post-publication cleanup refusal and retry, sibling substitution, bounded and
canonical refusal, activation rollback, unavailable acceleration, pointer
conflict, and all five durable crash phases. The complete selector passed 26
tests in 538.75 seconds. Scoped static gates are clean. All prior findings
remain closed. Verdict is **PASS** with no CRITICAL or HIGH finding.

## Recommendations

Proceed to S11 without weakening the journal, pointer, rollback, or candidate
cleanup boundaries established here.
