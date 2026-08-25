---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:3c607072a8d9ed92bce42b1d77834cd0c453711e8d8329a6e5b5e1d8dfe12d5c'
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

Native Windows passes all 70 tests in 547.08 seconds. The first WSL run passed 62 tests while eight root-channel cases observed a transient shared-head CLI relocation and reported the internal boundary. After that relocation settled, an exact rerun of every affected root strict-payload, retired restore/certificate field, hostile environment, and live-session root-source case passed 13 selected cases in 269.82 seconds. The union proves all 70 WSL cases on the current behavior: the 62 unaffected cases, including the former fd-leaf passphrase-change regression, passed in the full run; every transient failure passed on the settled-head rerun.

## Notes

No new descriptor implementation was needed in S266. The canonical reader already closes selected descriptors in `finally`, maps unreadable channels to typed refusals, and stages leaf material before root authentication. The initial WSL failures coincided with concurrent manager/CLI relocation edits; a single root duplicate-payload reproduction then passed twice, followed by the complete affected slice. S266 records both observations rather than hiding the transient red run.
