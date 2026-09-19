---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:5ddd584362c48a41ccb543566cea3e88bf8542bd0e463222ecc362cab197457e'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
---
# `tui-architecture` audit: `W08.P27.S392 Declarations workspace projection review`

## Scope

Independent review of the live immutable Declarations workspace projection and its contract tests. The review traced all three zone observations and source sets, availability/freshness/count truth, cross-bucket work/revision/filing/pointer joins, local filing versus AEAT evidence meaning, protected identities and sensitive payloads, lifecycle sanitization, deterministic order, frontend neutrality, and the strength of adversarial tests.

## Findings

### filed-revision-pointer-does-not-require-a-filing-record | high | Closed: filing pointers, records, and revision states now form one admitted fact

The initial projector accepted a work unit whose `filed_calculation_revision_id` remained set while `current_filing_record_id` was absent and the filing catalogue was empty. It emitted `has_current_filing=False`, `is_filed=True`, and zero filing rows.

Remediation requires the filed-revision and current-filing pointers to be present or absent together. When present, both must resolve to the same work unit, the current record must reference that exact revision and be `VIGENTE`, and the revision must be `PRESENTADO`. The reciprocal catalogue pass refuses a current filing not named by the work unit, requires every presented revision to have a current record, and requires every superseded revision to have a superseded record; superseded records also require a same-coordinate successor and superseded revision state.

A ten-case adversarial matrix now refuses filed-pointer-only, filing-pointer-only, missing revision, missing record, record/revision mismatch, non-current current record, non-presented filed revision, presented revision without record, current record without pointers, and a superseded record attached to a current revision. The original reproduced state is explicitly covered. This finding is closed.

## Positive findings

The three zone observations are total and canonically ordered; available and stale states require observation times, never-captured forbids one, and only observable zones expose measured counts. Unavailable and never-captured zones preserve unknown counts rather than false zero, while available empty is an exact zero. Zone source sets keep local declarations, calculations, filings, lifecycle, and AEAT evidence explicitly named. Filing rows keep local record status separate from AEAT acceptance and evidence kind, and the canonical filing model prevents an AEAT acceptance claim without persisted external evidence.

All protected bucket, work-unit, calculation-revision, filing-record, and lifecycle-fact identities are excluded from serialization and repr while natural Modelo/year/period coordinates remain available. Financial values, names, actors, NIFs, notes, and external references are absent. Lifecycle input is constrained to a payload-free closed kind, time, and protected identities. Rows are deterministically sorted by natural coordinates and chronology with identity tie-breakers, duplicate lifecycle identities and duplicate natural declaration addresses refuse, foreign buckets and orphan revisions refuse, and the function consumes only preloaded authorities. The defining module imports no adapters, entrypoints, repositories, filesystem or network clients and performs no I/O.

## Verification

Initial gates: 8 focused projection tests passed; Ruff and ty passed. Final remediation gates: all 18 focused projection tests passed, including the ten-case filing coherence matrix; Ruff and ty passed for the implementation and tests.

## Recommendation

CLOSE. The high cross-authority coherence finding is closed. W08.P27.S392 is safe to mark complete.
