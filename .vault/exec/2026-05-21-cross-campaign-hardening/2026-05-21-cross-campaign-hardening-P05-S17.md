---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P05.S17'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P05.S17`

Closed CALC-2: externally imported filing evidence now persists
registry-grounded `CasillaObservation` rows.

- Modified: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/application/modelo/test_import_flow.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Changed the external import path to retain the registry snapshot it
already resolved for casilla-id validation, then project every imported
casilla into a `CasillaObservation` using registry `legal_refs` and
`source_refs`. Formula provenance is intentionally absent for external
AEAT evidence, so the persisted observations carry `formula_id=None`
and empty operand fields.

Added a real import-flow regression that reads the persisted
`CalculationRevision` and asserts imported casillas have values plus
non-empty legal/source provenance.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_import_flow.py` passed.

`uv run pytest -q src/aeat/application/modelo/test_import_flow.py` passed with 21 tests in 32.05s.

`uv run pytest -q src/aeat/application/modelo/test_amend_flow.py::test_amend_revision_carries_casilla_observations` passed with 1 test in 22.10s.
