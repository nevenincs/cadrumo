---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b0dcaf97a5b6ec844d5d02fa515c0d4d73d22c7a7ca981f5bc20aa1d80dc5cae'
step_id: 'S24'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Refuse a persisted profile payload that omits schema_version at both read boundaries

## Scope

- `src/cadrumo/application/user_profile/_repository.py`

## Description

- Read the decrypted payload while it is still a mapping and refuse when it
  declares no schema version.
- Call the check at both persisted read sites, the record load and the snapshot
  load.
- Defer malformed bytes to the typed validation that already reports them with
  field-level detail.
- Prove the refusal by deleting the marker from a really-written payload.

## Outcome

Landed in `9691145bb41f971ce415a607072c2c3a3eea7159`, after the row was amended
from its original remedy.

The row originally asked for the field to be made required plus a sweep of every
construction site. That was measured at 231 sites across roughly 150 files, of
which two are production. The other 229 are in-memory test and harness
constructions, and an in-memory record omitting the field is not the defect: the
defect is a persisted payload hydrating as current because its stored bytes carry
no marker. The remedy was moved to where the defect lives.

The seam is the whole of this step. The field's default reads the schema
authority, so once typed validation has run the marker is present whether or not
the bytes carried it. A check placed after that point passes on every payload,
including every payload it exists to refuse -- which would have rebuilt, inside
this remedy, the exact defect the campaign was formed to remove. The check
therefore reads the raw decrypted JSON before validation, and inspects the INNER
record's marker rather than the envelope's own version field.

The snapshot half is defence in depth: that model's marker is already required
with no default, so an unstamped payload would fail typed validation regardless.
It is checked anyway so both read sites raise the same typed refusal, and so the
guarantee does not silently depend on that field never acquiring a default.

## Notes

**What this does NOT deliver.** It closes the READ boundary only. An in-memory
record constructed without the field still resolves it from the default factory,
so the unstamped state remains constructable even though it is no longer
readable from disk. Required-ness would have closed both. That limit is recorded
in the production docstring and the test docstring as well as here, so a later
reader cannot mistake this row for full required-ness.

**A third read site was found AFTER this row was first marked complete, and the
row was reopened.** The initial change guarded the two single-record reads,
because the boundary had been enumerated by searching for load methods rather
than for every place the typed model is built from stored bytes. The iterating
read hydrates every stored row of the namespace and the lifecycle service
consumes it to list live profiles, so an unstamped payload still hydrated as
current on the one path that enumerates everything. It is the most dangerous of
the three and it was the one missed.

The count is now established by pattern rather than by method name: three
hydration sites, no fourth, confirmed independently on both sides. Enumerate a
boundary by the OPERATION it performs, never by the names its methods happen to
carry.

**The iterating site refuses the walk rather than skipping the row.** A skip
returns a listing that is short and indistinguishable from complete, on a surface
whose only job is to enumerate what the operator has -- a profile absent from
every listing with nothing saying so. The plural read fails more quietly than the
singular one, because a partial collection has no shape a caller can inspect. The
neighbouring failure mode already refuses rather than dropping, so skipping would
have made one module answer the same question two ways.

**The premise this rests on, re-confirmed at HEAD rather than inherited.** No
production path can emit an unstamped record: one production construction site,
which stamps id and version from the loaded schema; no use of the
validation-bypassing construct in either profile package outside a single test
file; and the field's default deriving from the same authority. If a write path
ever appears that can emit an unstamped record, this remedy is insufficient and
required-ness returns.

The anti-tautology proofs delete the marker from really-written payloads and
assert refusal through the real repository. The iterating proof asserts a RAISE
rather than a count, because a count would pass against a guard that silently
dropped the row, and it forces the generator since the refusal surfaces only on
iteration. Each is guarded by a positive control asserting the writer stamped the
marker first, so no fixture can pass vacuously.

