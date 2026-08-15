---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:85604f2446a821d6e29bcd7db5ca091131636121e840b9211eed343406a6fea3'
step_id: 'S48'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether the profile values updated lifecycle event should have a production emitter, since the operator edit path writes facts while stamping strings that are not members of the event taxonomy, leaving the declared event with no emitter anywhere

## Scope

- `src/cadrumo/application/wizard/ and src/cadrumo/domain/buckets/`

## Description

- Enumerate every `event_type` stamped at every profile-fact write door and test each against the closed `BucketEventType` set.
- Trace the write path to the single point where the stamped string meets the taxonomy.
- Rule on whether `PROFILE_VALUES_UPDATED` should carry a production emitter, grounded in what the event taxonomy is for.

## Outcome

**RULING: yes. `PROFILE_VALUES_UPDATED` must have a production emitter, and it is the correct member for every profile-fact write door. It is not dead capacity and must not be removed.**

The grounds are structural, not stylistic. A profile-fact write emits exactly ONE bucket event; that event's id becomes the record row's `source_event_id`, and the read path refuses a row whose witness is missing. One mandatory event per record revision, binding the row, is by definition the data-change slot — the lifecycle slot. The taxonomy's own split puts the data change in the lifecycle event and the operator's verb invocation in a separate surface event, precisely so a later query can tell "these values changed" from "the operator invoked this verb". `PROFILE_VALUES_UPDATED` names the data change. Every door writes facts, and writing facts IS that data change, whichever surface collected them.

What the doors were stamping instead — `profile.wizard.answers.applied`, `profile.wizard.patch.applied`, `profile.manager.field.applied`, `profile.capability.changed` and siblings — are surface identities. They name which door was used, not what changed. They had been smuggled into the lifecycle slot, which can hold only one of the two axes. So the surface axis belongs in the event PAYLOAD, where a `door` key now carries it; the reserved payload keys are only the six lineage witnesses, so the key is free.

**The declared event therefore had no emitter for a reason that was itself the bug**, not because the concept was unused. Removing it would have deleted the one correct member and left the taxonomy describing only doors.

**Scale correction to the row's premise.** The row says the edit path stamps "strings that are not members of the event taxonomy", which is true but understates the reach. Measured against the 115-member enum: **12 call sites stamp 9 distinct non-member strings**, across the wizard package AND the CLI config surface. Only two stamped strings in the whole profile-fact family are valid members (`profile.censo.applied`, `profile.setup.completed`). This is a systemic taxonomy breach, not two stray sites.

The repair that follows from this ruling is recorded under `S152`.

## Notes

- The ruling was settled BEFORE the repair, because it decides the repair: had the answer been "no emitter", the correct action would have been deleting the member rather than repointing the doors.
- Naming was checked against the domain-stem mandate. No new event-type member was added, so no new AEAT-surface value entered the taxonomy — which is an argument in favour of the chosen repair over inventing members. The payload door values (`wizard.answers`, `wizard.patch`, `wizard.checkpoint`, `wizard.descendants`) are generic surface vocabulary with no AEAT counterpart. The reserved registry-input term was not used for anything.
- **What this ruling does NOT do:** it does not fix the six CLI config call sites. They are outside this agent's ownership and are enumerated in `S152` for dispatch. Until they are repointed, four operator-facing profile-edit verbs remain broken in exactly the way this ruling describes.
- No claim is made that a surface event now exists for these verbs. The ruling says the surface axis belongs somewhere other than the lifecycle event type, and parks it in the payload; whether these verbs additionally warrant their own surface events is a separate question that was not asked and was not answered.
