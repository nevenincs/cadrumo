---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:0051400dc80c6f7e155327b1cb296f368e63d6be0f9100fed730d5e7915526e6'
step_id: 'S25'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Bind the operator guide's account of what the censal pull fills to CENSAL_ADOPTABLE_PATHS with a both-directions parity gate, the page having promised the fiscal ID it never adopts while the ownership guard's deliberate first-read allowance kept the failure silent for a blank-identity operator

## Scope

- `docs/how-to/censo-update.md`

## Description

- Correct the operator guide's account of the censal pull so it no longer
  promises to fill the fiscal identity, which the pull reads to confirm
  ownership and never adopts.
- Bind the guide's claim to the adoptable-path tuple with a parity gate in both
  directions, so the page and the code cannot drift apart silently again.

## Outcome

The guide states what the pull fills and what it does not, and the claim is
enforced against the tuple rather than maintained by hand.

Landed as commit `299e1e988e`.

## Notes

This record was written during a plan reconciliation, from the commit and the
step text, rather than by whoever executed the work. It reports what landed and
what was verified; it does not speak for the reasoning behind the choices, which
only the executor holds.

The step was already marked complete when this was written, with no record
linked - the state the plan-closure rule exists to prevent. The record was
absent rather than misfiled: no document under the feature carried this step's
identifier or referenced the guide, checked with a positive control confirming
the search ran. So the checkbox was set without a record rather than a record
existing under a name the index could not match, and the repair is this document
rather than a rename.
