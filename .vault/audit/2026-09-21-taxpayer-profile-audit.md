---
tags:
  - '#audit'
  - '#taxpayer-profile'
date: '2026-09-21'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:1f23a225cb2a34c4bb4aa897673d0d2f8ee9026af3266fbea4fb30fe9d04e787'
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

### same-profile-stale-result | high | A delayed write result could repaint an older same-profile revision

The first P03 review found that the TUI rejected a result for another profile but accepted an older result for the same profile after a newer projection became visible. S07 was reopened. The settling boundary now compares revision and digest before repainting and discards the stale result with copy that preserves the possibility that its write completed. A direct delayed-result regression passes.

### repeatable-row-tui-usability | high | Add and remove were untyped and unexercised

The first P03 review found raw text controls for closed-set repeatable fields, an unidentified removal confirmation, and no direct add/remove tests. S07 was reopened. Add now uses schema-projected choices, removal names section and stable row, and direct tests cover empty-section add, canonical choice tokens, nonordinal removal, validation refusal, persistence failure, and persisted refresh.

### post-commit-refresh-outcome | medium | A projection failure after commit can still look like a failed write

Installed TUI composition publishes before rebuilding the overview. If the post-commit projection unexpectedly fails, generic failure copy can imply nothing was saved even though storage may have committed. No critical/high defect remains, but final reporting must retain this ambiguity rather than recommending a blind retry.

### profile-locale-boundary | low | One application projection still uses CLI-owned census leaf keys

The TUI row actions and missing-field summary now use TUI-owned flow keys. The application overview projection still resolves census divergence leaf labels from `cli.config.profile.*`; this is retained as low boundary debt and does not alter mutation semantics.

Phase P03 result after correction: PASS. Both high findings were fixed and the focused race suite passes 13 tests; no critical or high finding blocks installed acceptance.

### installed-no-op-evidence | high | Initial installed receipt did not audit the claimed no-op

The first P04 review rejected journey7 because its receipt did not retain typed no-op evidence and the TUI paths had no explicit no-op operation. A second review rejected journey8 because its child accepted any successful message. S10 was reopened. The visible TUI child now saves the already-visible value unchanged, requires the exact localized `flows.manager.edit.no_change` outcome, rejects `flows.manager.edit.saved`, and emits only `no_op_observed`; TUI-only and CLI-to-TUI both execute it. Journey9 aggregates that evidence with the CLI `changed=false` result and records `no_op_observed=true`. Positive and negative predicate regressions pass. The high finding is resolved.

### repository-import-gate | medium | Stable canonical gate remains red outside PROFILE-01

Two shared-worktree runs were invalidated by concurrent source changes. A clean detached worktree at commit `06e5524ce2` then produced a stable source snapshot with the canonical `just check-import-boundaries` command. It still reports ten unapproved findings in assets, calendar, income-tax, M303, workbench, quality, and ledger-test files, plus the shared `dev.acceptance` package declaration gap; no PROFILE-01 file occurs. This is an external integration dependency. S10 must remain open until the repository owner restores the gate; PROFILE-01 does not suppress, baseline, or absorb those findings.

P04 code/acceptance review result: PASS for PROFILE-01 behavior after the no-op correction. No unresolved critical or high product/acceptance finding remains. Plan close remains blocked solely by the required repository-wide import-boundary gate.

Final re-review at `26ba3fd5b3`: PASS. Journey9's receipt hash recomputes, both TUI-bearing mutation paths retain exactly one typed no-op observation, and the exact localized predicate plus negative saved-result regression close the prior high finding. The PR1-PR12 dispositions are conservative and accepted. No critical or high PROFILE-01 finding remains.

## Recommendations

- Fix clear projection at the shared projection boundary and add an anti-resurfacing regression before touching consumers.
- Keep PR6 blocked until a decision assigns prospective as-of resolution and durable filing snapshot pinning across profile, calendar, and tax workflows.
- Add the in-flight write plus F5 integration before claiming PR2 or PR5 entity-switch safety.
- Continue targeted discovery from the checkpoint until the configured Luna/RAG route becomes available; do not relabel fallback reads as semantic coverage.
