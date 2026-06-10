---
name: revision-resolution-is-law-determined
trigger: always_on
---

# Revision resolution is law-determined, never injected

## Rule

Every production calculation, verification, filing, export, or projection path
MUST resolve its registry revision from `(modelo, filing_year, period)` through
`ValidatedRegistryAuthority.snapshot` / `select_revision`
(`src/aeat/domain/calculations/registry/_temporal.py`) or
`resolve_registry_revision_for_work_target`
(`src/aeat/application/modelo/_work_addressing.py`); a stored, literal, or
operator-supplied `revision_id` may only be *asserted equal* to that resolution,
never injected as the selector.

## Why

ADR `2026-06-10-period-revision-resolution-adr` (ruling 1 / D1) ratifies
`select_revision` as the single law-determined period→revision resolver: AEAT
binds every `(modelo, filing_year, period)` triple to exactly one revision by
publishing orden, so "which revision applies" is a derived fact, not an input.
Feeding a stored `revision_id` back into resolution makes the stored value
*causal* on the computation — the defect class that lets one year's numbers be
computed under another year's norms. Comparing it against the resolver's answer
makes the law causal and the stored value a checked claim; the non-overlap gate
`validate_revision_windows` guarantees the resolution is unique, so a `revision_id`
narrowing can only equal the law-determined pick or refuse.

## How

- Good: a calc entry loads a WorkUnit, resolves the snapshot from its
  `filing_year` + `period`, then asserts equality —
  `if snapshot.revision.id != work_unit.revision_id:` raises an instructive
  refusal naming both revisions (`_calculation_actions.py:594`,
  `_calculate_input.py:265`). The unit's `revision_id` is compared, never passed
  into resolution.
- Good: a creation-time `--revision` is accepted only when it names exactly
  `select_revision(modelo, filing_year=year, period=period).id`
  (`resolve_registry_revision_for_work_target`); the explicit id is an
  assertion/idempotence handle, not a free override.
- Bad: passing `unit.revision_id` (or a literal) into `authority.snapshot(...)`
  on a calculation path so resolution is *selected* by the stored value — a
  silent legal mismatch when the registry's law-mapping was corrected after the
  unit was created.
