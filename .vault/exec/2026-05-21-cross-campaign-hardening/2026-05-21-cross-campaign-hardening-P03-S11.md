---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P03.S11'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P03.S11`

Closed XDOM-3: IVA compensation history now imports
`FiledDeclaracionObservation` from the public Sede adapter surface.

- Modified: `src/aeat/application/calculations/_iva_compensation_history.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Re-pointed the application calculation module from the private
`aeat.adapters.outbound.aeat.sede._schema` module to the public
`aeat.adapters.outbound.aeat.sede` package export. The public surface
already exported `FiledDeclaracionObservation`, so no adapter API change
was required.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.

`uv run pytest -q src/aeat/application/calculations/test_iva_compensation_history.py` passed with 7 tests in 1.70s.

`rg -n "from .*sede\\._schema import FiledDeclaracionObservation|sede\\._schema import \\(.*FiledDeclaracionObservation" src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/test_iva_compensation_history.py` found no remaining private import for `FiledDeclaracionObservation` in the touched calculation surface.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S11` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P03-S11.md src/aeat/application/calculations/_iva_compensation_history.py` passed with the existing plan-file CRLF normalization warning.
