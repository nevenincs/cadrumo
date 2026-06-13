---
tags:
  - '#adr'
  - '#modelo-inventory'
date: '2026-04-17'
modified: '2026-04-17'
related:
  - '[[2026-04-17-modelo-inventory-remediation-research]]'
  - '[[2026-04-13-modelo-inventory-adr]]'
  - '[[2026-04-13-modelo-inventory-plan]]'
---

# `modelo-inventory` adr: `regulatory-remediation-for-037-130-347-193-and-year-plan-parity` | (**status:** `accepted`)

## Problem Statement

Issue 108 was implemented and merged, but a post-merge regulatory audit
found that the current local modelo catalogue overstates some obligations,
omits one annualized retención model, and lets the `year-plan` runtime
surface drift from the registry taxonomy. The implementation is therefore
not yet accurate enough to claim full inventory completeness for the
identified autonomo and SL scenarios.

## Considerations

- The prior issue-108 registry is already public and used by CLI and tests.
- The project is under a strict pydantic mandate.
- The deadline engine is the runtime source for filing-history and
  `year-plan`.
- The user explicitly re-issued the original handover mandate with no
  human in the loop, so this ADR is accepted under that instruction
  instead of waiting for an approval round.
- The remediation should preserve historical knowledge where useful while
  correcting current guidance and runtime behaviour.

## Constraints

- No dataclasses may be introduced into the new `aeat.domain.modelos` work.
- Changes must remain within the issue-108 scope: inventory correctness,
  runtime applicability, CLI parity, and tests.
- The implementation must use official AEAT/BOE sources as the authority
  for the corrected behaviours.
- The runtime profile model should be widened only enough to express the
  audited cases, not turned into an open-ended compliance engine.

## Implementation

The remediation will apply these architectural decisions:

- Add `MODELO_193` to `ModeloCode` and materialise a strict
  `modelo_193` metadata entry.
- Rewire `modelo_123` so its annual relationship resolves to `193`
  instead of a deliberate gap marker.
- Keep `037` in the registry for historical and interpretive purposes,
  but revise its applicability and gotchas so it is no longer represented
  as the active current default after 2025-02-03.
- Enrich `aeat.domain.deadlines.AutonomoProfile` with dedicated flags for:
  professional retenciones,
  the `130` 70-percent professional withholding exception,
  and the `347` threshold condition.
- Update `aeat.domain.deadlines._applies` and `_calendar` to support `347` and
  the richer `130` / `111` / `190` runtime logic.
- Update the modelos CLI so `year-plan` and profile projection use the
  expanded runtime shape instead of overloading `has_employees`.
- Replace count-based and closed-set tests with behaviour-driven
  assertions that pin the corrected regulatory outcomes.

## Rationale

This option is the smallest change set that resolves the audited gaps
without widening issue 108 into unrelated tax-automation work.

- Preserving `037` as a known code avoids rewriting historical inventory
  knowledge while still stopping current misguidance.
- Adding `193` is necessary because the project already models `123` and
  claims annualized retenciones coverage.
- Widening the runtime profile is preferable to burying more caveats in
  metadata because the user-facing defect is in the actual `year-plan`
  output, not only in the docs.
- `347` belongs in the runtime engine because it is already part of the
  inventory and has a concrete annual deadline once the threshold is met.

## Consequences

- The enum is no longer fixed at twenty members; any tests or summaries
  that encoded that number must change.
- Some CLI flags and runtime model validations will expand.
- The remediation will invalidate portions of the original issue-108 audit
  and summary, so a fresh audit and exec summary are required.
- `037` remains in the registry, which means downstream consumers must
  treat it as historical knowledge rather than assume every registry entry
  is currently active.
