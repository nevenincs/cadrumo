---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:474ed741a96e6884079c3b5bfdcdc5de2bb33cda5621c2af435bc6e1f1374020'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` audit: `S08 committed discovery and retired-path review`

## Scope

Independent review of `W02.P03.S08` against the accepted custody roll-up and
lifecycle successor decisions and the completed S07 record. The review covered
the single custody discovery seam, exact existence-only retired-member
detection, typed refusal guidance, workflow discovery and health projections,
root and candidate link/reparse behavior, malformed current-marker handling,
real filesystem tests, and scoped static checks. S09, S10, production
remediation, and plan mutation were excluded.

## Findings

The detector itself is coherent. `list_current_profile_custody_capsule_ids` is
the sole application inventory seam and performs retired refusal before
anchored current-marker enumeration. The retired inventory is the closed exact
`manifest.toml` member; detection uses no-follow existence checks and never
opens or parses its bytes. A match raises `LEGACY_CUSTODY_DETECTED` with only
`DESTRUCTIVE_RESET` and `REENROLL_PROFILE`. UUID candidates with a present but
malformed current marker propagate a custody integrity error rather than being
silently skipped. POSIX uses directory descriptors and no-follow child opens;
Windows pins the root and candidate ancestry and refuses reparse candidates.
Workflow scan delegates to the committed repository and carries no manifest
reader or duplicate inventory authority.

### s08-health-retired-provider-probe | high | Cold health assessment still opens the retired master-key provider

`assess_active_profile_health_with_session` remains a live workflow path that
dynamically imports `get_master_key_provider` and enters that provider to retry
a cold active-profile read. Its own comments and error handling describe
keyring/master-key access as the recovery mechanism. This is exactly the
retired provider/keyring probe S08 is required to remove: health can still
consult a second custody authority after committed-capsule discovery, and its
result depends on provider availability. The focused health tests cover
malformed-marker projection but contain no negative observation proving zero
provider or keyring access, so the green selector does not close this boundary.

Verification evidence: custody discovery plus lifecycle tests pass 16 tests in
20.51 seconds, and workflow active-resolution plus health tests pass 14 tests
in 8.73 seconds. Scoped Ruff and Ty pass, and BasedPyright reports zero errors
and warnings. Those gates establish the detector's current happy and refusal
paths but do not override the live retired-provider call above. Verdict is
**FAIL** with one HIGH finding; S08 remains unchecked.

## Recommendations

Replace the cold-session retry with the current custody/session owner or return
a typed locked/unavailable health projection without probing any master-key or
legacy keyring authority. Remove the dynamic storage import and every
master-key/keyring-specific comment and exception branch from workflow health.
Add a real observation test through `assess_active_profile_health_with_session`
that proves no legacy provider/keyring operation occurs for ready, absent,
malformed-marker, and cold-session states while preserving typed reset or
re-enrollment guidance where retired artifacts are detected. Repeat exact
negative searches and the focused custody/workflow gates before re-review.

## Final remediation re-review

The HIGH finding is closed. The provider-opening wrapper is deleted, and
`assess_active_profile_health` is now observation-only: it reads an already
bound current record/session when present and returns the existing typed
unreadable-record projection for a cold session. Workflow contains no
`get_master_key_provider`, provider activation, keyring, password, unlock,
recovery, session-mint, or session-resume operation. Its only scoped
master-key mention is package documentation explicitly stating that workflow
does not handle it.

The real observation test constructs current capsules and filesystem states
before installing an audit hook and independent C-call profile observer. It
then assesses ready, absent, malformed-marker, and cold-session states through
the production health path. The ready case uses a real already-authenticated
custody session; the cold case has none. Configured secret-store directories
and hostile recovery-directory paths record zero stat, lstat, open, or read
operations. Assertions require `ready`, `none`, `capsule_unreadable`, and the
typed `profile_record_unreadable` cold result respectively. No mock, fake,
stub, monkeypatch, skip, or expected-failure shortcut appears in the scoped
tests.

Exact searches confirm the removed wrapper and retired provider calls are
absent from workflow. No manifest reader, writer, or parser exists in workflow,
the committed repository, or custody discovery; the only scoped manifest
matches define and explain the exact existence-only retired member. The
current-marker and link/reparse behavior reviewed above remains unchanged.
Obsolete registry or MCP schema references outside this boundary are deferred
peer work and neither provide a profile discovery path nor affect this verdict.

Verification evidence: the combined custody discovery, lifecycle, active
resolution, and health selector passes 31 tests in 25.43 seconds; the dedicated
four-state zero-secret/recovery observation test independently passes in 10.63
seconds. Scoped Ruff and Ty pass, and BasedPyright reports zero errors and
warnings. The executor's broader 39-test evidence is consistent with these
proportional reruns.

Final verdict: **PASS**. No CRITICAL or HIGH finding remains attributable to
`W02.P03.S08`. The executor is authorized to create exactly one S08 execution
record and canonically check S08 only. S09 and S10 remain out of scope.
