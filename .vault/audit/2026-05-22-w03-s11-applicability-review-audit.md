---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-21-taxpayer-type-applicability-adr]]'
  - '[[2026-05-21-taxpayer-type-applicability-research]]'
---

# `cli-workflow-redesign` Code Review

W03.S11-001 | LOW | Registry-owned applicability is coupled through private module imports

`src/aeat/domain/calculations/registry/_applicability.py:73` imports taxpayer model types from `aeat.domain.deadlines._models`, and `src/aeat/application/overview/_applicability.py:5` imports the moved rules from `aeat.domain.calculations.registry._applicability`. This keeps the current tests green and avoids the noted registry/deadlines package import cycle, but it leaves the new registry-owned rule surface dependent on private implementation modules across package boundaries. That conflicts with the local quality gate rejecting cross-package private imports and makes later deadline or registry package reshaping more fragile. Prefer a non-cyclic public surface for the shared taxpayer model/applicability contract, such as a public neutral model module or public registry applicability module that does not require exporting through registry `__init__`.

Residual risks: the review stayed inside the W03.S11 files requested. It did not review unrelated dirty changes in `src/aeat/domain/calculations/registry/__init__.py`. The seed rule legal references were checked by the new registry test for referential resolution, but this audit did not re-adjudicate every legal citation against BOE article text.

Gates observed during review: `uv run ruff check src/aeat/domain/calculations/registry/_applicability.py src/aeat/application/overview/_applicability.py src/aeat/domain/calculations/registry/test_modelo_applicability.py` passed; `uv run pytest src/aeat/domain/calculations/registry/test_modelo_applicability.py -q` passed with 3 tests.

W03.S11-002 | RESOLVED | Public non-cyclic applicability surfaces added

The private import coupling was resolved by adding `src/aeat/domain/deadlines/taxpayer_model.py` as the public taxpayer-model type surface and `src/aeat/domain/calculations/registry/applicability.py` as the public registry applicability surface. The registry-owned implementation now imports taxpayer model types through the public deadline module, and the overview compatibility wrapper imports the applicability API through the public registry module rather than the private implementation module. The fix deliberately still avoids exporting the applicability API through `registry.__init__`, because that path reintroduced the registry/deadlines circular import noted during implementation.

Resolution gates: `uv run ruff check src/aeat/domain/deadlines/taxpayer_model.py src/aeat/domain/calculations/registry/applicability.py src/aeat/domain/calculations/registry/_applicability.py src/aeat/application/overview/_applicability.py src/aeat/domain/calculations/registry/test_modelo_applicability.py` passed; `uv run pytest src/aeat/domain/calculations/registry/test_modelo_applicability.py src/aeat/application/overview/test_applicability.py -q` passed with 61 tests.
