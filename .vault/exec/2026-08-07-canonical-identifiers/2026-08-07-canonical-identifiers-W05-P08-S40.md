---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:83cb97240982a72838aa2d4a220bfd24bff721f3ff9c1a08403951edd63d6625'
step_id: 'S40'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype the three `registry_snapshot_id` sites and the `registry_revision_id` sites onto the two new aliases

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Description

- Retyped the `registry_snapshot_id` half, the three sites confirmed real
  during `W05.P08.S38`:
  `domain.calculations.registry._snapshot_coordinate.registry_snapshot_id`
  and `registry_snapshot_id_for` now return `RegistrySnapshotId` instead of
  bare `str`, and
  `adapters.outbound.aeat.sede._schema.FiledDeclaracionObservation
  .registry_snapshot_id` is now `RegistrySnapshotId | None`, dropping the
  now-redundant inline `Field(min_length=1, max_length=128)` since the
  alias already carries that exact bound.
- Did NOT retype any `registry_revision_id` site: `W05.P08.S39`'s record
  established there is nothing bare left — every site already carries
  `RevisionId`, and minting `RegistryRevisionId` to retype onto would
  fragment the canonical type `W05.P07.S36` just consolidated. This row's
  own two-alias premise is therefore half current, half stale; executed
  the current half, declined the stale half with the reasoning already on
  record in `S39` rather than repeating it here.
- Checked for an import cycle before adding `from ....core.identity import
  RegistrySnapshotId` to a `domain/calculations/registry/` module: `core`
  imports nothing from `domain`, so the direction is safe.

## Outcome

COMPLETE for the live half of the row (`registry_snapshot_id`, 3/3 sites).
The `registry_revision_id` half is correctly NOT executed — see `S39`.
`ruff check`, `ruff format --check` clean on both touched files;
`basedpyright` clean on `_snapshot_coordinate.py` (gated); `_schema.py`
sits outside basedpyright's configured `include` (`domain`, `application`
only). Real tests green: `test_snapshot_coordinate.py` (part of a 16-test
sweep with the sede observation-store roundtrip suites, all passing) and a
broader `adapters/outbound/aeat/sede/tests/` run (787 passed, 7 failed —
all seven pre-existing, in a currently-dirty test file
(`test_declarations_part2.py`, live peer WIP) or exercising XML-dictionary
/ export-layout logic this row never touched; confirmed by `git status`
showing the implicated production files clean, and by content — none of
the seven failures reference `registry_snapshot_id`, `RegistrySnapshotId`,
or any identity type).

## Notes

No incidents. `registry_snapshot_id_for`'s existing docstring already
correctly describes the return value; no docstring changes were needed
beyond the signature.
