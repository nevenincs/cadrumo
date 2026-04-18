---
tags:
  - '#plan'
  - '#draft-approval-staleness'
date: '2026-04-18'
related:
  - '[[2026-04-18-draft-approval-staleness-adr]]'
  - '[[2026-04-18-draft-approval-staleness-research]]'
  - '[[2026-04-17-kent-revise-review-audit]]'
---

# `draft-approval-staleness` `implementation` plan

Implement persisted draft approval provenance and deterministic stale detection
for issue #230 without destabilizing the current filing build/validate flow.
The change must add an approval surface for review, recompute approval-basis
fingerprints against current upstream state, and block downstream submit flows
when a previously approved draft has gone stale.

## Proposed Changes

Add review-approval data structures to `src/aeat/filing/_schema.py` and expose
stable helpers in `src/aeat/filing` for:

- building canonical approval-basis fingerprints
- approving a draft
- recomputing current review state for a persisted draft
- clearing or replacing stale approval provenance when re-approved

Thread that review state through the relevant CLI and submission surfaces:

- add a review CLI entrypoint for approval and review-state inspection
- surface approval state in filing display/list flows where operators already
  inspect drafts
- reject submit preflight when the draft is unapproved or stale
- align submission/workflow protocol shims so `READY_TO_SUBMIT` alone cannot
  bypass review gating

Add focused tests around JSON draft round-trip, approval persistence, stale
transitions after transaction mutations, and submit-gate behaviour.

## Tasks

- `Phase 1: Review provenance model and hashing helpers`
  1. Add approval data structures and serialization support to
     `src/aeat/filing/_schema.py`.
  2. Implement canonical fingerprint helpers for payload, validation surface,
     transaction catalogue, category profiles, and schema/formula provenance in
     the filing domain.
  3. Add review-state helpers that derive `unapproved`, `approved`, or `stale`
     from the stored approval record and freshly recomputed basis.

- `Phase 2: Review CLI and draft surfaces`
  1. Add `aeat review approve <draft_id>` and supporting helpers under
     `src/aeat/cli/review`.
  2. Register the new review command in `src/aeat/cli/__init__.py`.
  3. Update filing show/list output so operators can see approval and stale
     state on persisted drafts without needing to inspect raw JSON.

- `Phase 3: Submission and workflow enforcement`
  1. Update submit preflight helpers in `src/aeat/submission/_preflight.py` to
     require both `READY_TO_SUBMIT` and a non-stale approval result.
  2. Align `src/aeat/submission/_protocols.py` and
     `src/aeat/workflow/_engine.py` with the new review-state check so legacy
     protocol assumptions cannot bypass approval gating.
  3. Keep existing non-approval build/validate flows unchanged apart from the
     new approval awareness.

- `Phase 4: Verification coverage`
  1. Extend filing-domain tests for approval persistence and JSON round-trip.
  2. Add a real-behaviour stale-detection test that mutates the transaction
     catalogue after approval and proves the draft becomes stale.
  3. Add submit/preflight tests proving unapproved and stale drafts are blocked
     while freshly approved drafts still pass the review gate.

## Parallelization

Phase 1 is the critical path because the CLI and submit gate both depend on the
shared approval-basis helpers. Once the review-state helpers are in place, CLI
surface work and submit-gate work can proceed mostly independently before the
verification pass.

## Verification

Mission success requires:

- persisted drafts round-trip with approval provenance intact
- approving a `READY_TO_SUBMIT` draft stores `approved_at`, `approved_by`,
  `approval_basis`, and `review_checksum`
- changing the underlying transaction catalogue after approval produces a stale
  review result without rebuilding approval provenance
- submit preflight rejects unapproved or stale drafts
- existing non-review build and validate flows continue to work

Primary verification will be through targeted unit tests in the filing and
submission domains plus at least one CLI-level approval test that exercises the
real JSON draft storage path. If the current branch lacks a dedicated export
surface, submit and draft-inspection paths remain the enforced review boundary
for this issue.
