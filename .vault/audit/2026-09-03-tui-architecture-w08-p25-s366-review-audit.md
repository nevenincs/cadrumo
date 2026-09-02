---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:21a64fbeded0c35a04fee3991464c778e8151977c22d7a9a8566c07ffe0e749e'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-tui-architecture-w08-p25-s365-review-audit]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
  - "[[2026-09-02-unreachable-capability-tui-homepage-product-design-research]]"
---



# `tui-architecture` audit: `w08 p25 s366 review`

## Scope

Independent review of `W08.P25.S366` in `src/cadrumo/application/overview/home.py`
and `src/cadrumo/application/overview/tests/test_home.py` against the exact plan
row, the accepted Home navigation decision and product research, and the closed
`HomeProjectionV1` contract delivered by `S365`. The review concentrated on
reader authority, local-only behavior, unavailable-state mismatches,
deterministic ranking, declaration vocabulary and focused-test teeth.

The composer has no repository, adapter, frontend or network dependency and
performs no implicit I/O. Its final construction through `HomeProjectionV1`
correctly refuses non-available zones that still carry rows or counts, while
unobservable AEAT evidence is reduced to `NOT_OBSERVED`. The focused suite
passed with 7 tests and Ruff passed for both reviewed files. Those green gates
do not close the authority and determinism findings below.

## Findings

### declaration-authority | high | A raw WorkUnit fallback creates a second declaration authority

`HomeProjectionInput` accepts both exact `HomeDeclarationResume` rows and raw
domain `WorkUnit` records. `_project_declarations` independently translates
every work unit into a Home lifecycle claim, then lets exact rows overwrite only
matching identifiers. An authoritative empty or partial declaration-reader
result is therefore indistinguishable from an absent reader: omitted identifiers
are silently repopulated from the fallback. This conflicts with the exact Step,
which names canonical declaration readers, and with the accepted decision to
compose existing application projections rather than reimplement them in Home.

The fallback can also make a materially wrong claim. Any non-discarded work unit
becomes `DRAFT`, including one that already carries a calculation revision or a
filing-record pointer. The comment acknowledges that richer state belongs to the
exact reader, but emitting `DRAFT` is still a positive lifecycle assertion; the
work unit proves only its own `BORRADOR`/`DESCARTADO` axis. The same seam exposes
the rejected internal `WorkUnit` name and its much wider domain record at a
public Home-composition input, even though the output correctly uses
declaration vocabulary. S366 should consume one canonical declaration projection
only, or represent absence of that projection explicitly and refuse to invent
rows.

### tie-determinism | medium | Equal ranking keys and duplicate declaration identities remain input-order dependent

Action sorting uses rank, reason, action identifier and natural address, but
omits `DeclaredNextAction.argument_bindings`. Two distinct executable actions
can consequently compare equal and change which payload survives the top-three
cut when their input order changes. Declaration merging has the same last-write
shape: duplicate work-unit identities within either input, or a conflict between
the two inputs, are silently selected by tuple order rather than rejected as an
authority inconsistency. A deterministic preview needs a complete semantic key
or a uniqueness/refusal invariant, not incidental stable-sort and dictionary
insertion behavior.

### composition-test-teeth | medium | The focused suite cannot detect the principal authority and ordering failures

The work-unit helper derives the same identifier for both the nominally older
and newer rows. The assertion that only `newer` remains is therefore caused by
dictionary overwrite, not by declaration ordering, and it normalizes an
impossible duplicate-identity catalogue instead of testing two declarations.
There is no case for a work unit carrying a filing pointer, authoritative empty
declaration output alongside fallback rows, conflicting duplicate identities,
or action ties that differ only in argument bindings. State-mismatch coverage
reaches Ledger and one declaration case but not actions, agenda or Messages.
Finally, checking that field names omit `repository`, `client` and `reader`
cannot prove absence of I/O; the current implementation is pure by inspection,
but that test would stay green if I/O entered through a differently named global
or helper.

### s365-relocation-governance | medium | The contract moved but its plan path and focused proof did not move with it

Current HEAD intentionally folds the S365 projection records into `home.py` and
deletes `home_projection.py`. The result has one canonical definition and no
runtime import split, but the approved plan still credits S365 to the deleted
module while S366 names only the composer module. The relocation also deleted
the 12-test S365 contract file rather than migrating its direct negative cases.
The remaining S366 suite exercises composition well, but no longer directly
bites several model invariants that the S365 review required: stale observation
time, session-posture shape, Ledger subset bounds, declaration year agreement,
Messages zero under unavailable authority, and contradictory direct projection
construction. This is a plan/evidence mismatch rather than a new runtime
authority defect, but the owning rows cannot be considered fully traceable until
the plan and tests describe the live canonical home.

### remediation-disposition | low | Exact reader authority and complete deterministic ties close the production findings

Final re-review confirms that `work_units` and the WorkUnit imports and lifecycle
translation are gone. `HomeProjectionInput` now accepts only exact declaration
rows and refuses duplicate `work_unit_id` values. Action ordering uses a
canonical JSON identity over every semantic field except the incoming rank, so
argument bindings participate in ties; duplicate semantic actions are refused
before preview trimming. The tests now prove both permutation-independent action
ties and duplicate refusal, and the focused suite passes with 9 tests. The
composer remains local-only and its final `HomeProjectionV1` construction
enforces unavailable-zone mismatches and AEAT-evidence masking.

Accordingly, `declaration-authority` and `tie-determinism` are closed. No
critical or high-severity finding remains. The relocation/test-proof mismatch
above remains medium severity.

## Recommendations

1. Remove the raw `work_units` input and `_project_declarations` lifecycle
   inference. Feed the composer only the canonical declaration-reader
   projection, with availability expressing when that reader has no authority.
2. Define complete deterministic action tie behavior and reject duplicate or
   conflicting declaration identities instead of resolving them by input order.
3. Replace the duplicate-ID fixture with distinct valid declarations and add
   bite-proven tests for the authority conflict, filing-pointer case, ranking
   ties and each zone mismatch branch.
4. Do not credit `W08.P25.S366` while `declaration-authority` remains open. No
   critical finding remains; one high-severity finding remains.
5. Final remediation closes recommendations 1 through 3 and supersedes the
   initial recommendation 4 disposition: no high or critical finding remains.
6. Reconcile the S365 plan path with the intentional canonical-module fold and
   migrate the deleted direct S365 invariant tests into the live owning test
   module before treating the combined S365/S366 evidence as complete.
