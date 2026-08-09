---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:30b99a7f257a5baab3b6a44390c983dd65c0ce518994ad233f9424219f777504'
step_id: 'S44'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Give the Art. 81.1 qualifying months month identity rather than a bare count

## Scope

- `src/cadrumo/domain/contribuyente/family.py`
- `src/cadrumo/domain/contribuyente/_descendant_facts.py`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`
- `src/cadrumo/application/wizard/`

## Description

- Persist the Art. 81.1 qualifying-month identity as `meses_madre_trabajo` rather than a scalar count.
- Parse and expose the month-set grammar through the CLI and wizard entry surfaces.
- Intersect the mother-work and nursery-attendance month sets in the guardería calculation path.
- Reconcile commits `664ac0511d`, `303e744401`, and `b03870b1ef` against current HEAD.

## Outcome

The persisted profile carries exact qualifying months, and `guarderia_simultaneous_meses()` computes the statutory overlap instead of using the minimum of unrelated counts. The committed CLI grammar accepts individual months and ranges, the wizard persists the same shape, and current HEAD retains the behavior with no target-file drift.

## Verification

Focused real persistence, grammar, proration, wizard, CLI, and injection lane:

`uv run --no-sync pytest -n 0 -q <S44 targeted paths>`

`124 passed, 21 deselected in 14.81s`

## Notes

This is a backfilled execution record for behavior landed before the plan row was reconciled. No production or test file changed during the backfill. Unrelated active WIP in `application/wizard/_status.py` was not touched.
