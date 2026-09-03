---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:09481919e4220376450857b376187c50ba544e32636dafb8f06ea544c8e141e7'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
---
# `tui-architecture` audit: `W08.P27.S392 Declarations workspace projection review`

## Scope

Independent review of the live immutable Declarations workspace projection and its contract tests. The review traced all three zone observations and source sets, availability/freshness/count truth, cross-bucket work/revision/filing/pointer joins, local filing versus AEAT evidence meaning, protected identities and sensitive payloads, lifecycle sanitization, deterministic order, frontend neutrality, and the strength of adversarial tests.

## Findings

### filed-revision-pointer-does-not-require-a-filing-record | high | Open: the projection can assert a filed revision with no filing authority

`_validate_catalogue_joins` proves that a non-null `filed_calculation_revision_id` resolves to a revision owned by the work unit, but it does not require any filing record for that pointer. It separately permits `current_filing_record_id` to be `None`. The revision row then derives `is_filed` solely from the dangling semantic pointer.

A live adversarial probe used otherwise valid canonical objects, removed the work unit's current filing pointer and supplied an empty filing catalogue while retaining its filed-calculation pointer. `project_declarations_workspace` accepted the snapshot and emitted `has_current_filing=False`, `calculation_revision.is_filed=True`, and zero filing rows. This is a contradictory legal-history projection: the UI can state that a revision is filed while the canonical filing-record authority supplies no filing event.

Require every `filed_calculation_revision_id` to be backed by the coherent current filing record for the same work unit and calculation revision, with the record `VIGENTE` and the revision in the filed state. Conversely, a current filing pointer must remain paired with that filed revision pointer. Add adversarial tests for the missing filing record, a missing current pointer, a pointer to a non-current or wrong revision, and a current pointer whose record is not current. The tests must use individually valid authorities and vary only their cross-catalog join.

## Positive findings

The three zone observations are total and canonically ordered; available and stale states require observation times, never-captured forbids one, and only observable zones expose measured counts. Unavailable and never-captured zones preserve unknown counts rather than false zero, while available empty is an exact zero. Zone source sets keep local declarations, calculations, filings, lifecycle, and AEAT evidence explicitly named. Filing rows keep local record status separate from AEAT acceptance and evidence kind, and the canonical filing model prevents an AEAT acceptance claim without persisted external evidence.

All protected bucket, work-unit, calculation-revision, filing-record, and lifecycle-fact identities are excluded from serialization and repr while natural Modelo/year/period coordinates remain available. Financial values, names, actors, NIFs, notes, and external references are absent. Lifecycle input is constrained to a payload-free closed kind, time, and protected identities. Rows are deterministically sorted by natural coordinates and chronology with identity tie-breakers, duplicate lifecycle identities and duplicate natural declaration addresses refuse, foreign buckets and orphan revisions refuse, and the function consumes only preloaded authorities. The defining module imports no adapters, entrypoints, repositories, filesystem or network clients and performs no I/O.

## Verification

All 8 focused projection tests passed. Ruff passed for the implementation and tests. ty passed for the implementation and tests. The green suite does not discharge the high finding because it checks orphan revisions and foreign work buckets but has no adversarial filing-pointer matrix; the direct probe reproduced the contradictory accepted output.

## Recommendation

Do not close W08.P27.S392 until the high cross-authority coherence finding is remediated and covered by non-vacuous adversarial tests.
