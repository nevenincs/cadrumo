---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S06'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---




# DONE. Both committed release pointers, the bucket manifest and the tap formula, are guarded against a backward bump before the push commits, because ordinary merge semantics can otherwise resurrect an older pointer and un-publish a newer version with no workflow failing. Ported from the sort -V shell idiom that vaultspec-core and vaultspec-dashboard each reinvented independently, into a tested module handling both pointer shapes, reading the formula version from its release-asset URL since the generated formula carries no version stanza, comparing numerically so 0.2.10 correctly beats 0.2.9, and refusing an unreadable pointer rather than treating it as absent, which is the failure mode that would silently disable the guard exactly when repository state is unexpected. Twenty-nine real-behaviour tests over real files, and the workflow gate pins that the guard reads the clone before the copy, since checking after would compare the file with itself

## Scope

- `dev/packaging/release_pointer_guard.py`
- `dev/packaging/tests/test_release_pointer_guard.py`
- `.github/workflows/publish-release.yml`

## Description

- Port the backward-bump guard from the sibling products' shell idiom into a tested module.
- Parse the Scoop pointer's version from its JSON key and the Homebrew pointer's from its release-asset URL, since the generated formula carries no version stanza.
- Refuse an unreadable pointer rather than reading it as absent.
- Compare numerically so a double-digit patch version is ordered correctly.
- Run the guard in both channel pushes against the clone, before the new pointer is copied over it.
- Pin the guard's placement with a workflow gate asserting it precedes the copy.

## Outcome

Both committed release pointers are guarded. A publication that would move a channel backward refuses and names both versions and the consequence, rather than succeeding and silently un-publishing the newer version for every user resolving that channel.

Twenty-nine tests, all against real files through the real module and its command-line entry point, including both generator-shaped pointer texts, the numeric-ordering pair that a string comparison would invert, and the exit statuses the workflow actually consumes.

## Notes

The load-bearing decision is that an unparseable pointer refuses rather than passing as absent. Treating it as absent would disable the guard exactly when repository state is unexpected, which is the only situation it exists for, and it would do so invisibly. Seven malformed-pointer shapes are pinned as refusals.

The Homebrew version had to be read from the release-asset URL because the generated formula has no `version` stanza. That makes the extraction sensitive to the generator's URL shape, so it is anchored on the releases-download path segment and a test proves an unrelated resource URL in the same formula is not mistaken for it. If the formula generator ever emits a version stanza, the guard should read that instead.

Placement matters as much as presence: the guard must read the clone before the cohort file is copied over it, because checking afterwards would compare the file with itself and pass unconditionally. The workflow gate asserts the ordering rather than merely the guard's presence.

This is the one place where two sibling products independently reinvented the same guard, which is what earned it a place in the shared mechanism rather than either product's private patch.
