---
tags:
  - '#audit'
  - '#taxpayer-profile'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:a00052330bda14f62863d919525f05148f27c2e685d46a839cebcbae735e1385'
related:
  - "[[2026-09-21-taxpayer-profile-plan]]"
---

# `taxpayer-profile` audit: `integrated PROFILE-01 execution review`

## Scope

Phase P01 audit artifacts and focused runtime evidence were reviewed against PROFILE-01, the approved taxpayer-profile plan, and the accepted profile session, record, setup-flow, wizard, and completion decisions. The review covers ownership safety, the bounded field matrix, representative fact trace, focused risk reproductions, and historical-context escalation. No product implementation was part of P01.

## Findings

### clear-projection | medium | A later explicit clear resurfaces an older dated value

The focused synthetic probe confirms `record_to_path_values` filters the clear after ordering rather than resolving the latest fact first. Clear-aware census reconciliation remains correct, but value consumers can receive the older value. P02.S04 already owns the canonical projection fix and permanent regression test, so P01 needs no reopening.

### historical-context | medium | Production filing pinning and as-of profile resolution are absent

The audit found types and persistence ports but no production profile-snapshot creator/save caller. Modelo binding loads the current record. The checkpoint correctly refuses to invent semantics, records bounded options, and leaves PR6 blocked pending a cross-lane decision. This is an uncovered product capability, not an unrecorded implementation choice.

### switch-concurrency | low | Ordinary F5 revocation passes but an in-flight profile write is untested

The TUI test proves successful handover revokes the old composed root. It does not prove the worker-thread write transition. P03.S07 names that missing integration explicitly; no current acceptance claim relies on it.

### discovery-route | low | Mandatory semantic and Luna discovery routes were unavailable

The checkpoint records two stopped Luna attempts and the accelerator-bound RAG service failure. The lead stayed within the policy fallback by using retained preflight evidence and targeted reads. Confidence is appropriately limited rather than overstated.

Result: PASS. No critical or high review finding blocks P02.

### clear-projection-closure | low | Shared current-value projections now agree on explicit clears

Phase P02 resolves the latest fact per path before dropping null values. The regression covers path-keyed, selector-keyed, and typed Modelo indexes while the effective-fact projection still exposes the clear and provenance. Focused CLI and census tests confirm the writer and reconciliation contracts remain aligned. No parallel projection or consumer-specific workaround was introduced.

### persistence-boundary-review | low | Projection repair leaves custody and filing provenance owners intact

The implementation changes only `application/user_profile/projections.py` and its owning test. Snapshot canonicality, required event emission, real-path profile binding, absent-fact handling, and profile-derived export identity all pass. No secure-object namespace, repository, event type, or Modelo source was changed. Production snapshot pinning remains honestly blocked rather than inferred from passing snapshot unit tests.

Phase P02 result: PASS. No critical or high finding blocks frontend work.

## Recommendations

- Fix clear projection at the shared projection boundary and add an anti-resurfacing regression before touching consumers.
- Keep PR6 blocked until a decision assigns prospective as-of resolution and durable filing snapshot pinning across profile, calendar, and tax workflows.
- Add the in-flight write plus F5 integration before claiming PR2 or PR5 entity-switch safety.
- Continue targeted discovery from the checkpoint until the configured Luna/RAG route becomes available; do not relabel fallback reads as semantic coverage.
