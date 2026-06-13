---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P08.S33'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P08.S33`

Closed CALC-7.

- Modified: `src/aeat/application/workflow/_protocols.py`
- Modified: `src/aeat/application/workflow/__init__.py`
- Modified: `src/aeat/application/workflow/_engine.py`
- Modified: `src/aeat/application/workflow/test_engine.py`
- Modified: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/application/modelo/test_file_flow.py`
- Verified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Tightened `ModeloInputsProviderProtocol.load_inputs` from
`Mapping[str, object]` to the exported `ModeloInputs` contract:
`Mapping[str, str | Decimal]`.

The workflow engine now stores provider output as `ModeloInputs`, and
the revision-backed providers in the Modelo application flow and its
integration tests return the same narrowed contract. The draft builder
surface still accepts `Mapping[str, object]`; a `Mapping` of
`str | Decimal` values is a valid narrower producer for that consumer.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/application/workflow/_protocols.py src/aeat/application/workflow/__init__.py src/aeat/application/workflow/_engine.py src/aeat/application/workflow/test_engine.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_file_flow.py` passed.

`uv run ty check src/aeat/application/workflow/_protocols.py src/aeat/application/workflow/_engine.py src/aeat/application/modelo/_actions.py src/aeat/application/workflow/test_engine.py src/aeat/application/modelo/test_file_flow.py` passed.

`uv run pytest src/aeat/application/workflow/test_engine.py -q` passed with 33 tests in 97.02s.

`uv run pytest src/aeat/application/modelo/test_file_flow.py -q` passed with 29 tests in 77.90s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S33` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P08-S33.md src/aeat/application/workflow/_protocols.py src/aeat/application/workflow/__init__.py src/aeat/application/workflow/_engine.py src/aeat/application/workflow/test_engine.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_file_flow.py` passed.
