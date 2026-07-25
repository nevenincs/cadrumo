---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S62'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace scoped reset with start, status, and resume over all live, tombstoned, and dangling-pointer targets

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Remove the previous scope-based reset surface entirely and expose exactly three operations: `start_config_reset`, `config_reset_status`, and `resume_config_reset`.
- Discover targets by listing profile buckets with tombstoned buckets included, then adding the active-pointer bucket identifier so a dangling pointer whose bucket is already absent still becomes an explicit target.
- Capture a pointer snapshot correlating presence, bucket identity, and content digest before any mutation.
- Refuse a start while another journal is incomplete, surfacing an already-running error naming the incomplete operation.
- Build the initial preflight into a durable journal and persist it exclusively before any roll-forward, so the target set and its retention decisions exist on disk before the first irreversible act.
- Return a paused operation without mutating when the preflight cannot resolve retention for every target.
- Make `config_reset_status` a pure read returning one journal by identifier or the latest journal, raising a typed not-found error rather than creating or repairing anything.
- Require explicit confirmation on both start and resume through a typed confirmation-required error.
- Declare typed errors for confirmation, already-running, and not-found conditions, and register them in the error registry.

## Outcome

- The reset surface is now a single durable operation addressed by identifier, replacing the previous scoped reset with no alias, wrapper, or compatibility path retained.
- Discovery covers live, tombstoned, and dangling-pointer targets while excluding root-level artefacts that are not buckets, so a stale pointer cannot survive a completed reset.
- Status is structurally incapable of mutating: it constructs a repository and loads, with no save on any path.
- The journal is written before roll-forward begins, so a crash immediately after start still leaves a resumable record of the intended target set.
- Landed in commit `60135859e2`, with the resume loop and validators decomposed into named helpers in `9851e08ae8`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- A repository-wide search confirms no scoped-reset symbol survives anywhere in the source tree, so the replacement is a hard cutover rather than a parallel surface.
