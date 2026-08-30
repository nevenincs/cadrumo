---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:d077c9f0e17d0c531699357751e6ea54206340654046923dd184c025ffebef22'
step_id: 'S122'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Extract the self-verifying custody digest base into a leaf module so every custody record can reach it, the two capsule records having been unable to subclass it where it lived

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Changes

- `A` `src/cadrumo/adapters/persistence/storage/custody/digest_model.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/label_head_models.py`
- `verify:` `pytest src/cadrumo/adapters/persistence/storage/custody -n 0` -> `pass` (238)

## Notes

A triage sweep reported five custody records hand-rolling a self-digest shape a
base class already generalises, and said the dependency direction allowed the
two capsule records to subclass it. Checked: the direction is the reverse.
`label_head_models` imports `ProfileCustodyCapsuleLabel` FROM `capsule_records`,
so those two subclassing it where it lived would have closed an import cycle.

The base is therefore extracted to a leaf module that imports nothing from its
siblings. This Step is the relocation only -- behaviour-neutral, and the two
existing subclasses still resolve. Extending it with the field validator, the
mismatch check and the canonical payload, then moving the five records onto it,
is tracked separately: these records verify encrypted profile-password custody,
so each move needs its digest proved unchanged rather than assumed.
