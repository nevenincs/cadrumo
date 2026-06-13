---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-live-shape-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Borrador snapshot management list, discard, export, verify` | (**status:** `accepted`)

## Problem Statement

`aeat app live borrador 100 fetch` captures an AEAT borrador snapshot;
`aeat app live borrador 100 show SNAPSHOT_ID` displays one. The
`borrador-100-binding-integration` ADR locks how a snapshot is consumed by
`calculate --borrador SNAPSHOT_ID`. But there is no verb to list existing
snapshots, no verb to discard stale ones, no verb to export a snapshot for
records, and no verb to validate a snapshot before feeding it to
calculate. Operators refreshing their borrador over the tax year
accumulate orphan snapshots with no management surface.

## Considerations

- Borrador snapshots are immutable AEAT-sourced data with a capture
  timestamp. They cannot be edited; only refreshed (new capture) or
  discarded (mark stale).
- An operator who fetched a snapshot early in the year may need to
  re-fetch later as AEAT updates the datos-fiscales; the new snapshot
  supersedes the older for calculation purposes.
- Pre-calculate validation surfaces incomplete snapshots (missing
  `aeat_prefilled = true` casillas) before the operator runs a calculate
  that would fail mid-pipeline.
- Documentary export gives operators a snapshot file for their tax folder
  independent of the bucket's internal storage.

## Constraints

- `aeat app live borrador 100 list` enumerates snapshots in the active
  bucket, with capture timestamp, year, state (`current` / `superseded`
  / `discarded`), and counterpart counts.
- `aeat app live borrador 100 verify SNAPSHOT_ID` runs a read-only
  completeness check against the registry's `aeat_prefilled = true`
  binding set; output names any missing casillas with the readiness
  category that would block `calculate`.
- `aeat app live borrador 100 discard SNAPSHOT_ID --by ACTOR
  [--reason TEXT]` transitions the snapshot to `discarded` state and
  emits a bucket event. Discarded snapshots are excluded from
  `calculate --borrador` selection and from default `list` output.
- `aeat app live borrador 100 export SNAPSHOT_ID --output PATH
  [--format json|pdf]` writes the snapshot to a local file. The `pdf`
  format is reserved; `json` is the canonical machine-readable form.
- All four verbs are read-only against AEAT; no live AEAT contact occurs
  during list / verify / discard / export. (`fetch` remains the only
  live-contact verb in the borrador surface.)
- Discard cannot be applied to a snapshot already consumed by a
  `verified_complete` or `filed` modelo revision; the rejection error
  names the offending revision id.

## Implementation

Command shapes:

```text
aeat app live borrador 100 list [--year YYYY] [--state current|superseded|discarded|all]
                                [--format json|text]
aeat app live borrador 100 verify SNAPSHOT_ID [--format json|text]
aeat app live borrador 100 discard SNAPSHOT_ID --by ACTOR
                                              [--reason TEXT]
                                              [--format json|text]
aeat app live borrador 100 export SNAPSHOT_ID --output PATH
                                              [--format json|pdf]
```

Pipelines:

- `list`: query the borrador snapshot repository for the active bucket;
  enrich each row with its consumed-by-revision count from the
  calculation source-trace index.
- `verify`: load the snapshot; resolve the modelo 100 registry's
  `aeat_prefilled = true` binding set; produce a readiness report.
- `discard`: verify the snapshot is not consumed by any verified/filed
  revision; mark `discarded`; emit `live.borrador100.discarded`.
- `export`: serialise the snapshot payload (and capture metadata) to the
  requested format; do not include the bucket's encryption envelope.

Default behaviours:

- `list` defaults to `--state current` (excludes superseded and
  discarded).
- `--state all` shows the full history.
- `discard --dry-run` reports the closure (consumption check) without
  applying the state transition.

## Rationale

The borrador integration is the highest-value Modelo 100 UX hook. Without
list / verify / discard / export, the snapshot lifecycle is a black box.
List makes the set discoverable; verify catches incompleteness before
calculate fails mid-pipeline; discard cleans the candidate set for
`calculate --borrador`; export gives operators a documentary copy
independent of bucket storage. The audit-trail guard prevents discarding
snapshots cited by durable modelo revisions.

## Consequences

- The borrador application repository gains four new read/mutation paths;
  storage is unaffected (the underlying `live.borrador100.snapshot_captured`
  event already records every fetch).
- The bucket event history adds `live.borrador100.discarded` to the
  per-service emission scope.
- `aeat app live borrador 100 fetch` success output footer recommends
  `aeat app live borrador 100 verify SNAPSHOT_ID` as the next step before
  running calculate.
- Tests must cover: list filters by year and state; verify reports
  missing aeat_prefilled casillas; discard refuses on consumed snapshots;
  discard emits the expected bucket event; export writes JSON snapshot
  files faithful to the original capture; dry-run discard reports the
  consumption check without mutation.
