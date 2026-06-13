---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S04'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P01.S04 - ADR coverage classification

Scope: classify every proposed interface change as accepted ADR covered or new ADR required before implementation.

## Description

- Classify modelo lifecycle extraction against the accepted natural-key addressing ADR.
- Classify calculation extraction against the accepted natural-key addressing ADR and prior code-review residuals.
- Classify resume exact-id compatibility and natural-key migration against the accepted ADR.
- Define cases that require a new ADR before implementation.

## Outcome

Covered by the accepted ADR:

- Moving business logic out of CLI modules and into backend application services.
- Keeping internal content-addressed IDs authoritative for audit, replay, storage, and machine consumers.
- Making active profile or bucket plus modelo, year, and period the common operator-facing target.
- Preserving raw IDs as advanced exact-addressing escape hatches.
- Supporting `work resume` with exact UUID or exact work identifier as legacy compatibility.
- Adding natural-key `work resume` support through modelo, year, period, and explicit selectors once lifecycle and calculation semantics are stable.

Requires a new ADR before implementation:

- Adding hidden persistent selection state such as a default `work use` context.
- Promoting a new legally meaningful selector axis into filing identity.
- Changing storage identity for work units or calculation revisions.
- Allowing ambiguity to guess instead of refuse.
- Making exact IDs the primary operator-facing route again.

## Notes

This gate applies continuously. Future design questions that are not explicitly covered above must go through the VaultSpec ADR pipeline before code changes.
