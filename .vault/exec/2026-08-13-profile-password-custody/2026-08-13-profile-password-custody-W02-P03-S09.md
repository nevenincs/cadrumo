---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:3213d5b0ed4d82a7471f690398ef09528ed40e7832b7f4a407ac9765e2d2991e'
step_id: 'S09'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-14-profile-password-custody-s09-phase-review-audit]]"
---

# Review lifecycle discovery projection provenance selection and local-delete authority

## Scope

- `src/cadrumo/application/user_profile/`

## Description

- Review S07 and S08 as one lifecycle, semantic-state, discovery, selection,
  projection, and local-delete authority graph.
- Verify private physical and semantic write capabilities, authenticated record
  revision/event provenance, and observation-only locked discovery.
- Verify the governed label head, exact initial transaction witness,
  root-then-profile locking, crash recovery, and same-UUID substitution refusal.
- Run proportional real custody, transaction, lifecycle, record, workflow, and
  static-analysis gates and classify the peer collection blocker separately.

## Outcome

The phase review passed with no attributable CRITICAL or HIGH finding. Current
capsules are the sole physical and discovery authority; profile facts remain
session-bound to the one encrypted record and atomic event history; selection
uses pointer compare-and-swap; and local deletion retains its holds, owner
receipts, crash recovery, and local-only boundary.

Mutable labels now carry a separately governed current head. Locked reads
reconstruct the initial head only from the exact durable creation journal,
renames use a pending advance under root-then-profile locking, mixed crash
states refuse or recover deterministically, and a fresh canonical same-UUID
substitution is rejected. Locked and unlocked projections carry label
provenance, while unlocked facts additionally carry record revision and digest.

Proportional verification passed 42 custody/authority tests and 18
lifecycle/record tests. Ruff and Ty passed, and BasedPyright reported zero
errors and warnings. Independent Sol review approved the phase boundary.

## Notes

Full-suite collection remained unavailable because peer-owned
`domain/modelos/_calculation_revision.py` lacks its `StrEnum` import. That
failure occurs outside this phase and was not counted as either positive S09
evidence or an S09 regression. No production data or external service was
modified, and S10 was not started.
