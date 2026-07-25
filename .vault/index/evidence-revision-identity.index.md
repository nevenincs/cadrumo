---
generated: true
tags:
  - '#index'
  - '#evidence-revision-identity'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - '[[2026-07-24-evidence-revision-identity-adr]]'
  - '[[2026-07-25-evidence-revision-identity-S01]]'
  - '[[2026-07-25-evidence-revision-identity-S02]]'
  - '[[2026-07-25-evidence-revision-identity-S03]]'
  - '[[2026-07-25-evidence-revision-identity-operator-walkthrough-audit]]'
  - '[[2026-07-25-evidence-revision-identity-plan]]'
  - '[[2026-07-25-evidence-revision-identity-supersede-identity-conflict-audit]]'
  - '[[2026-07-25-evidence-revision-identity-supersede-implementation-findings-audit]]'
---

# `evidence-revision-identity` feature index

Auto-generated index of all documents tagged with `#evidence-revision-identity`.

## Documents

### adr

- `2026-07-24-evidence-revision-identity-adr` - `evidence-revision-identity` adr: `bundled evidence and calculation revision identity` | (**status:** `accepted`)

### audit

- `2026-07-25-evidence-revision-identity-operator-walkthrough-audit` - `evidence-revision-identity` audit: `operator walkthrough`
- `2026-07-25-evidence-revision-identity-supersede-identity-conflict-audit` - `evidence-revision-identity` audit: `the supersede transition the ADR mandates is unrepresentable under the revision-id invariant`
- `2026-07-25-evidence-revision-identity-supersede-implementation-findings-audit` - `evidence-revision-identity` audit: `what the supersede design meets in the code`

### exec

- `2026-07-25-evidence-revision-identity-S01` - Refuse a DESCARTADO unit in create_work_unit with an instructive message naming its state and a real next step, in the WorkUnitMutationRefusedError shape the same module already uses eleven lines below, rather than returning the discarded unit and letting every downstream verb deny it exists
- `2026-07-25-evidence-revision-identity-S02` - Gate that a discarded unit refuses at create and that the refusal names its state, closing the asymmetry where list_work_units hides a discarded unit by default while create_work_unit hands it back
- `2026-07-25-evidence-revision-identity-S03` - BLOCKED ON OPERATOR, the supersede transition as specified cannot be built, it carries the same inputs so it re-derives the id it is escaping and hits the amendment path's existing no-op refusal, and the escape requires a discriminator inside revision identity which this ADR reserves for operator sign-off

### plan

- `2026-07-25-evidence-revision-identity-plan` - `evidence-revision-identity` plan
