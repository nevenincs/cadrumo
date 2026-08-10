---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:483a54e0253784cc45c597c57da474834b0f58cc7f87643081353ab4cd9bf968'
step_id: 'S01'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Require exact schema id and schema version 4 for UserProfileRecord and UserProfileSnapshot

## Scope

- `src/cadrumo/domain/user_profile/_values.py`

## Description

- Replace the ceiling in the shared payload-identity validator with exact
  equality, so a pre-current version refuses where it previously passed.
- Derive the live record's default version from the loaded schema instead of the
  hardcoded literal it carried.
- Rewrite the validator docstring, which argued FOR the ceiling on the grounds
  that pinning would refuse the records this codebase writes.

## Outcome

Landed in `b409fa2` together with its proof step. The one shared validator serves
both the live aggregate and the immutable snapshot, so a single change covers
both surfaces and no second authority appears.

The defect was arithmetic in shape and asymmetric in effect: the check compared
the claimed version as greater-than the canonical one, which refuses a future
payload while silently accepting every older one. The live record then defaulted
to version 1 against a canonical 4, so the default this codebase wrote was
itself three versions pre-current and the ceiling waved it through. The snapshot
already required its version and copied the record's, so the stale default
propagated into snapshots as well.

The default now reads the loaded schema rather than naming a number, so a schema
advance moves behaviour without a sweep through call sites.

## Notes

Residual, and the reason a further row exists: this closes the pre-current and
future directions but NOT the omitted one. A persisted payload carrying no
version key still hydrates at the canonical version, because the field retains a
default. Closing that requires making the field required, which the live
aggregate could not absorb here -- 231 construction sites across roughly 150
files, all but two of them tests and development harnesses owned by other
campaigns. That work is rowed separately rather than folded into the change that
surfaced it, so it has an owner instead of living in a note.
