---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:55b473addb9064a1a85707af8b9b2141035e11af1a3e1725838561adca37d578'
step_id: 'S02'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Verify the frontend lane passes on a runner under Node 22, its first run refused npm ci because jest-dom 7.0.0 requires node 22 and the manifest under-declares at 20.19

## Scope

- `.github/workflows/frontend.yml`

## Description

- Push the accumulated commits so a dispatch would test current code rather than a stale remote tip.
- Dispatch the frontend lane against the pushed tip.
- Confirm the run reached a real runner rather than being cancelled while queued.
- Confirm the node version actually provisioned, not the version the job label advertises.

## Outcome

The lane passes on a runner. The row is satisfied.

The originating failure was that the dependency install refused because a test-library
dependency requires a node major the manifest under-declared. That step now succeeds,
which is the specific evidence the row asks for rather than a general green.

One detail would mislead a later reader and is worth recording. The job displays a
label naming the previous node major, which does not reflect what ran: the workflow
pins the newer major, and the provisioning step succeeded under it. The label is stale
display text. Anyone verifying this row from the run listing alone would conclude the
wrong thing.

The run also proves the fleet can serve this lane, which was in doubt earlier in the
session when the only capable runner was offline and three lanes were unsatisfiable.

## Verification

    run 31128691218  conclusion=success  runner=cadrumo-linux-x64-1  steps=10

    3. Provision Node                success
    4. Install locked dependencies   success   <- the previously refusing step
    5. Typecheck and build           success
    6. Test                          success

Workflow pin confirmed by reading the committed workflow rather than the job label:

    node-version: "22"

## Notes

The run reached a runner, which had to be checked rather than assumed. Earlier
dispatches in this session recorded a conclusion of failure while never executing a
single step, because they were cancelled while queued. A conclusion alone does not
distinguish a lane that ran and failed from one that never started; the discriminator
is a non-empty runner name and a non-zero step count.
