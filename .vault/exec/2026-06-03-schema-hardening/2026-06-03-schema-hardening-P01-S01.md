---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S01'
related:
  - "[[2026-06-03-registry-construct-pressure-plan]]"
---

# Audit M200 construct fragment split boundaries

## Scope

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records`

## Description

- Check the target records directory for local diff before auditing.
- Measure line counts and row widths for the M200 2024-and-later records
  fragments.
- Inspect `constructs.part-002.toml` for construct shape, array boundaries, and
  trailing member arrays.
- Confirm generic same-id construct merge support in `_loader.py`.
- Confirm existing loader coverage for split construct member arrays.
- Record the P01.S01 boundary audit and code-review audit.

## Outcome

- Safe split boundary identified for P02.S02. `constructs.part-002.toml` is the
  only current pressure file in the target directory at 1,465 lines, and the
  pressure is concentrated in the `casillas` array.
- P02.S02 should mechanically split only `constructs.part-002.toml`, preserve
  casilla order, and rely on existing generic same-id construct fragment merge
  semantics.
- No registry TOML, loader, schema, or validation code was changed in this step.

## Notes

- `vault add exec --feature registry-construct-pressure` was not used because
  this new continuation feature has no same-feature ADR. The step record is kept
  under the existing schema-hardening exec feature and linked to the
  construct-pressure plan rather than creating a fake ADR for an audit-only
  continuation.
