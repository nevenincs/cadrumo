---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S11'
related:
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-21-taxpayer-type-applicability-adr]]'
  - '[[2026-05-21-taxpayer-type-applicability-research]]'
  - '[[2026-05-22-w03-s11-applicability-review-audit]]'
---

# `cli-workflow-redesign` `W03.S11`

Registered the seed per-entity and per-regime modelo applicability
rules under the calculation registry package and kept the overview
surface as a compatibility consumer.

- Modified: `src/aeat/application/overview/_applicability.py`
- Created: `src/aeat/domain/calculations/registry/_applicability.py`
- Created: `src/aeat/domain/calculations/registry/applicability.py`
- Created: `src/aeat/domain/calculations/registry/test_modelo_applicability.py`
- Created: `src/aeat/domain/deadlines/taxpayer_model.py`
- Created: `.vault/audit/2026-05-22-w03-s11-applicability-review.md`

## Description

The modelo applicability rule table now lives in
`src/aeat/domain/calculations/registry/_applicability.py`, with a
public non-cyclic access surface at
`src/aeat/domain/calculations/registry/applicability.py`. The overview
module keeps the previous import surface by re-exporting the registry
API, so application behavior and tests continue to consume the same
functions and verdict types.

The registry-owned seed table covers the core taxpayer applicability
set for Modelos `100`, `111`, `115`, `130`, `131`, `180`, `184`,
`190`, `200`, `202`, `303`, `347`, `349`, and `390`. Each rule
carries scoped `legal_refs`, and the new registry test verifies that
those refs resolve in the legal catalogue. The new
`src/aeat/domain/deadlines/taxpayer_model.py` module exposes the
taxpayer model types without routing through the deadline package
initializer, avoiding the registry/deadline circular import found
during implementation.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_applicability.py src/aeat/application/overview/test_applicability.py -q`
  passed with 61 tests.
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_applicability.py src/aeat/domain/calculations/registry/test_schedules.py src/aeat/domain/deadlines/test_engine.py src/aeat/application/overview/test_applicability.py src/aeat/application/overview/test_calendar.py -q`
  passed with 160 tests.
- `uv run ruff check src/aeat/domain/deadlines/taxpayer_model.py src/aeat/domain/calculations/registry/applicability.py src/aeat/domain/calculations/registry/_applicability.py src/aeat/application/overview/_applicability.py src/aeat/domain/calculations/registry/test_modelo_applicability.py .vault/audit/2026-05-22-w03-s11-applicability-review.md`
  passed.
- `uv run aeat app registry verify` reported `Verificado=True`.

The mandatory review found one LOW issue about private module imports;
it was resolved with the public non-cyclic surfaces above, and the
follow-up review reported no new findings.
