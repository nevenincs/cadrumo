---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:017ef3ac0ea47d405c7475dc34e10d08107fbe1946b54d2ec62d1e8ffa27ac89'
step_id: 'S266'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Restore typed fail-closed machine-secret descriptor behavior so Windows root refusals never become unexpected internal boundaries and WSL passphrase change through the fd leaf succeeds while preserving descriptor consumption

## Scope

- `src/cadrumo/entrypoints/cli/ and src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

Run the full machine-secret subprocess contract serially on native Windows and WSL/POSIX. Verify typed root-channel refusals, descriptor closure or deliberate non-consumption, retired-field refusal, hostile-environment isolation, certificate and restore channels, and passphrase change through the file-descriptor leaf.

## Outcome

Native Windows passes all 70 tests in 547.08 seconds. A single immutable WSL/POSIX run from committed source identity `efe9ef0807` passes all 70 tests in 1,697.86 seconds. That complete run covers typed root and leaf refusals, descriptor consumption and deliberate non-consumption, hostile-environment isolation, certificate and restore channels, recovery handoff, and the fd-leaf passphrase-change case. No union of partial runs is used as closure evidence.

## Notes

No new descriptor implementation was needed in S266. The canonical reader already closes selected descriptors in `finally`, maps unreadable channels to typed refusals, and stages leaf material before root authentication. Two attempted full WSL runs in the principal shared tree were invalidated by concurrent source changes: the first crossed an emitter rename and failed 11 cases on a missing `_emit_envelope` import; the second crossed later settings/profile edits and failed 49 cases. The authoritative rerun used a plain `git archive` of `efe9ef0807` plus an isolated WSL uv environment, so every subprocess imported one fixed tree. The archive was not a Git worktree and had no branch or index; both the archive and isolated environment are removed after evidence capture and their absence is verified.
