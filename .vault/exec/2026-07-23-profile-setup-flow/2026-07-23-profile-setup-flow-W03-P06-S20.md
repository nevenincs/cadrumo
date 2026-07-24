---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S20'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Implement the create-mode checkpoint port over incremental effective-dated facts with derived-cursor resume and lifecycle discard

## Scope

- `src/cadrumo/application/wizard/_persistence.py`

## Description

Executed by a dispatched executor; verified and closed by the
coordinator.

- `ProfileFactsCheckpointStore` implements the substrate CheckpointStore
  port over the lifecycle authority: save mints-if-absent as
  SETUP_INCOMPLETE (else upserts facts), load offers resume only while
  incomplete (facts re-projected to answers), discard reuses the
  lifecycle/composition erase arms.
- Checkpoint declaration flipped to CREATE:AVAILABLE (save-and-exit is
  live) with MODIFY:UNAVAILABLE unchanged (loud refusal pinned).
- New atomic repository `complete_setup` flips record AND manifest
  together — closing a manifest-mirror gap in the earlier
  lifecycle-only arm (the plaintext manifest could stay
  SETUP_INCOMPLETE over an ACTIVE record); production completion now
  routes through it.
- Resume UX: a create naming a label whose profile is SETUP_INCOMPLETE
  resumes it (prior answers seeded); an ACTIVE label still refuses as
  duplicate; same-NIF re-create resumes rather than duplicating.

## Outcome

Commit `e8ffb2042f` (10 files). Coordinator verification: store suite
13/13 + event-emission contract 2/2 at HEAD; executor's runs 522/523
(the 1 red peer-owned: untracked status-screen WIP's flows.status keys).
ADR persistence bullet amended in place to the as-landed mint boundary
(first persistence event), with the per-answer tax-id mint recorded as
an explicitly-conditioned refinement (requires deferring the schema
required-field check while SETUP_INCOMPLETE).

## Notes

Open follow-ups tracked: per-answer early mint (validator relaxation
design), cursor-at-first-unanswered via resume_state threading (resume
currently seeds prefills; the store->resume_flow projection is
structurally tested), an explicit CLI discard affordance (rides the
entrada routing page step), and one queued locale key
(`application.wizard.notices.setup_saved_resume_later`) for the
coordinator's lane.
