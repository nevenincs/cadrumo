---
step_id: S98
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-30-identity-primitives-adr]]"
---

# core-authority W12.P29.S98 step record

## Step

Declare `BundleId` alias in `core/identity/_bundle.py`, re-export through `core/identity/__init__`, delete the `application/evidence/_ids.py` declaration, and update all callers. (RELOC-037, Rule 1)

## Status

BLOCKED — relocation not justified by Rule 1 cross-consumption criterion.

## Blocking rationale

Pre-execution cross-consumption audit found zero consumers of `BundleId` outside
`application/evidence/`. The identity-primitives ADR Rule 6 explicitly placed
`BundleId` in `application/evidence/_ids.py` with the rationale: "Hex-64 shape,
minted in the evidence application service, with no domain-layer owner. The
application layer is the lowest layer that owns the constraint."

Rule 1 clause (a) requires the alias to be "imported by code outside the declaring
layer" to trigger promotion to `core/`. With zero cross-layer consumers the trigger
condition is not satisfied.

The action-tracker RELOC-037 entry says "varies" for consumer count; the live grep
confirms 0 cross-layer consumers. Promotion would violate the identity-primitives ADR
without any architectural gain.

## Follow-up condition

If a future surface in `domain/`, `adapters/`, or `entrypoints/` begins consuming
`BundleId`, Rule 1 clause (a) is satisfied and the relocation becomes mandatory.

## Files touched

None.
