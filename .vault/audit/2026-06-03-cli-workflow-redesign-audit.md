---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-06-03-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` audit: `W83.P400.S2281 setup-event emission inventory`

Closure inventory for plan Step W83.P400.S2281. The Step names five
required setup-emission events plus two optional ones. Five emission
sites already exist in production paths; the remaining two are
dormant enum members whose operator paths do not exist yet. This
audit records the inventory so the Step can be ticked with structural
evidence rather than re-investigation.

## Required events — wired

The five required events surface from existing application-layer
paths. The inventory below is regression-gated by
`src/aeat/application/setup/test_s2281_event_emission_inventory.py`
which fails-loud if the named symbol leaves the named module.

### `profile.bucket.created`

Emitted from `ProfileLifecycleService.register` at
`src/aeat/application/user_profile/_lifecycle.py:99`. The same write
covers the `bucket.created` and `profile.created` semantics the plan
row lists separately: a profile registration is the act that creates
the bucket directory AND writes the inaugural profile record in one
atomic create span, so a single `PROFILE_BUCKET_CREATED` event
captures both. The plan-row enumeration ("bucket.created,
profile.created") was authored before the consolidation landed; the
test gate documents the merge so a future agent does not look for a
separate `PROFILE_CREATED` slot and add a duplicate.

### `profile.activated`

Emitted from `_append_profile_activated_event` at
`src/aeat/application/user_profile/_orchestration.py:277` and
`:291`. The two call sites cover the two activation paths: the
explicit `select_profile_with_lifecycle_span` flow and the implicit
register-then-activate flow on first-profile creation.

### `profile.values.updated`

Emitted from `ProfileLifecycleService.edit_field` and `edit_section`
at `src/aeat/application/user_profile/_lifecycle.py:106`, `:152`,
and `:173`. The lifecycle service also emits the sibling
`PROFILE_VALUES_CLEARED` when the edit removes a fact instead of
upserting one; the discriminator is the new value's nullness.

### `auth.provider.configured`

Emitted from the operator-auth configure flow at
`src/aeat/application/auth/_operator.py:315` and `:328`. The two
call sites cover the configure and re-configure cases.

## Optional events — dormant

The plan row marks two events optional, prefixed in the row text as
"optional config.env.updated, setup.state.migrated". Both events are
declared in the closed `BucketEventType` catalogue at
`src/aeat/domain/buckets/_event.py:112` and `:113` but neither has an
operator path today:

- `config.env.updated` would emit when an operator-driven environment
  configuration mutation lands (something like `aeat config env set`).
  No such verb exists; the codebase reads env config through
  `aeat.core.config.Settings` and there is no operator-facing
  env-mutation surface to bind the emission to.

- `setup.state.migrated` would emit when a first-run / migration
  path converts an older config layout to the current one. The
  current setup application carries no such migration; first-run is
  greenfield and there is no historical layout to migrate from.

Both enum slots stay declared so a future env-management or
setup-migration verb can wire its emission without re-litigating the
enum design. The test gate
`test_dormant_optional_events_remain_in_the_closed_catalogue` pins
the slots' presence so a refactor sweep does not silently retract
them.

## Conclusion

W83.P400.S2281 closes structurally: the 5 required events are wired
with regression-gated inventory, and the 2 optional events are
documented as dormant with no current operator path. The Step does
not require code changes this turn. If a future operator-facing env
or setup-migration verb lands, its emission wires the dormant pair
and the inventory test grows accordingly.
