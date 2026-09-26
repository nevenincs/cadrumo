---
tags:
  - '#reference'
  - '#tui-registry-api-gate'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:7919a4df8539b6cae8828535f0d0cbf0bfc862bf3b2a095e00837ff3227a0ae2'
related: []
---

# `tui-registry-api-gate` reference: `Active-profile pointer revision readers and storage bounds`

This record maps where the active-profile pointer's transition revision is produced, stored, bounded and read, measured against the tree on 2026-09-24. It grounds the decision on which successor revision to publish when the stored record cannot be read.

## Summary

### Producer

- Every successor is the observed predecessor plus one. It is published under the custody-root lock by the one pointer transaction (`src/cadrumo/application/user_profile/profile_pointer.py:66`, `src/cadrumo/application/user_profile/profile_pointer.py:144`).
- `clear()` publishes an absent tombstone instead of deleting the record (`src/cadrumo/application/user_profile/profile_pointer.py:61`).
- A missing record reads as the cold start at revision zero (`src/cadrumo/core/bucket_pointer.py:202`).
- A present record that does not decode, parse or validate raises `ActiveProfilePointerError`, carrying the path (`src/cadrumo/core/bucket_pointer.py:188`).

### Storage bounds

- The field is `int` with `ge=0` and no upper bound (`src/cadrumo/core/bucket_pointer.py:48`).
- It is serialised as a TOML integer, which is signed 64-bit, by the project TOML codec (`src/cadrumo/core/bucket_pointer.py:24`).
- The record is refused above 1024 bytes (`src/cadrumo/core/bucket_pointer.py:110`). A 19-digit revision stays far inside that bound.
- `time.time_ns()` fits in a signed 64-bit integer until the year 2262.

### Readers

- **Journals.** The login handover journal (`src/cadrumo/application/user_profile/login_handover.py:62`), the config-reset reconciler (`src/cadrumo/application/config_reset.py:404`) and the custody-service journal (`src/cadrumo/application/user_profile/custody_service.py:456`) each require exactly `before + 1` of a predecessor they read themselves. None of them compares revisions across a transition it did not perform.
- **Settings cache.** It keys on `(root, selection, bucket_id, transition_revision)` and does no arithmetic on the revision (`src/cadrumo/core/config.py:1040`).
- **WORK capture.** Its pointer limb hashes the record's stat fingerprint, not its revision, and assigns its own process-local generation (`src/cadrumo/application/modelo/work_addressing.py:1036`, `src/cadrumo/application/modelo/work_addressing.py:1049`).
- **Conclusion.** No reader assumes the revision is small or contiguous across a transition it did not observe.

### Lower bounds that survive corruption

The login handover journal records `pointer_before` and `pointer_after` (`src/cadrumo/application/user_profile/login_handover.py:51`). The config-reset operation records its pointer snapshot (`src/cadrumo/application/config_reset.py:400`). When present, each gives a lower bound for the lost revision; neither is guaranteed to be present.

### Reachability today

`aeat config repair profile --clear-active --yes` against a corrupt record exits before parsing. Authority admission builds settings, and settings composition reads the pointer (`src/cadrumo/application/provisioning.py:122`, `src/cadrumo/core/config.py:1091`, `src/cadrumo/core/_config_runtime.py:14`).
