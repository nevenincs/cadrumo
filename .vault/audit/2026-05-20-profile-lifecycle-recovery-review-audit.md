---
tags:
  - '#audit'
  - '#profile-lifecycle-disaster'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-19-profile-lifecycle-disaster-plan]]'
  - '[[2026-05-19-profile-lifecycle-disaster-adr]]'
  - '[[2026-05-19-profile-lifecycle-disaster-axis-a-session-activation-research]]'
---

# `profile-lifecycle-disaster` Code Review

PROFILE-RECOVERY-001 | HIGH | Manifest-only buckets must not be recreated by `profile create`
`profile create NAME` briefly allowed a missing secure profile record under an existing manifest to be recreated in place. This violated the ADR rule that manifest presence is the profile existence claim. Resolved by restoring manifest-based duplicate refusal and removing the rehydration test.

PROFILE-RECOVERY-002 | HIGH | Named active repair must clear the active pointer when explicitly confirmed
`repair profile --profile ACTIVE --clear-active --yes` previously reported status and exited before calling pointer repair. Resolved by routing named active clear requests through `repair_active_profile_pointer` and adding a CLI behavior test for the confirmed path.

PROFILE-RECOVERY-003 | MEDIUM | Profile show and switch must structure unreadable-record failures
`profile switch` and `profile show` only handled missing records. Decryption, envelope, classification, or validation failures could fall through to the unexpected boundary. Resolved by emitting a `profile_record_unreadable` report for generic read failures on both paths.
