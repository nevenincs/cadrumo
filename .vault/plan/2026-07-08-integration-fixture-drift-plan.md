---
tags:
  - '#plan'
  - '#integration-fixture-drift'
date: '2026-07-08'
modified: '2026-07-09'
tier: L2
related:
  - '[[2026-07-08-gate-drift-reconciliation-audit]]'
  - '[[2026-07-08-gate-drift-reconciliation-plan]]'
---

# `integration-fixture-drift` plan

### Phase `P01` - migrate non-UUID profile and bucket id constants

The uuid-profile-identities sweep left test constants like _BUCKET_ID and profile_id as human-readable strings; migrate them to UUIDs (the single largest cluster, ~18 failures).

- [x] `P01.S01` - Migrate the round5 bucket-id and profile-id string constants to UUIDs; `src/aeat/entrypoints/cli/_config/tests/test_auth_round5_surface.py`.
- [x] `P01.S02` - Sweep remaining non-UUID profile-id and bucket-id literals across the CLI and config test suite to UUIDs; `src/aeat/entrypoints/cli/tests/`.

### Phase `P02` - sweep remaining profile-create identity-flag drift

Add the required entity-type/name/surnames flags to the profile-create test helpers still missing them (~9 failures), extending the reconciliation P03.S13/S31 fixes.

- [x] `P02.S03` - Add the required identity flags to the remaining profile-create test helpers; `src/aeat/entrypoints/cli/tests/`.

### Phase `P03` - repair the bucket-session activation gap

Some isolated-backend fixtures create a profile but leave no active bucket session, so subsequent verbs refuse; activate/switch the session in those fixtures (~4 failures).

- [x] `P03.S04` - Activate the bucket session in the isolated-backend fixtures that leave none open; `src/aeat/entrypoints/cli/_config/tests/test_repair_reset_progress.py`.

### Phase `P04` - triage and drain the long-tail residual

Classify the remaining ~48 integration failures as fixture-drift (fix) or production-drift (route to a decision), file by file.

- [x] `P04.S05` - Triage the residual long-tail integration failures into fixture-drift versus production-drift, file by file; `src/aeat/entrypoints/cli/tests/`.
- [x] `P04.S06` - Route confirmed production-drift failures (calendar degrade/live-event/field-rename, agent-eval contradiction) to an opus decision or a documented defer; `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`.

## Description

## Steps

## Parallelization

## Verification
