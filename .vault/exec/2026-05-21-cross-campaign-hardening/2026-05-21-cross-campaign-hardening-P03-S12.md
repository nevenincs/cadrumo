---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P03.S12'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P03.S12`

Closed XDOM-4: profile-key normalisation is now available from the
public `domain.profile` surface.

- Modified: `src/aeat/domain/profile/_normalise.py`
- Modified: `src/aeat/domain/profile/__init__.py`
- Modified: `src/aeat/domain/profile/_keys.py`
- Modified: `src/aeat/domain/profile/test_normalise.py`
- Modified: `src/aeat/application/workflow/_utils.py`
- Modified: `src/aeat/application/review/_actions.py`
- Modified: `src/aeat/application/review/_models.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Added public `normalise_key` and exported it from
`aeat.domain.profile`. Re-pointed the profile-key registry, workflow
utility module, and review application code to the public symbol.
The private `_normalise_key` alias remains inside `_normalise.py` for
compatibility while no application module imports it.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/domain/profile/__init__.py src/aeat/domain/profile/_normalise.py src/aeat/domain/profile/_keys.py src/aeat/domain/profile/test_normalise.py src/aeat/application/workflow/_utils.py src/aeat/application/review/_actions.py src/aeat/application/review/_models.py` passed.

`uv run pytest -q src/aeat/domain/profile/test_normalise.py src/aeat/application/review/test_adapters.py src/aeat/application/review/test_aggregator.py` passed with 38 tests in 6.54s.

`rg -n "from .*domain\\.profile\\._normalise|from .*workflow\\._utils import _normalise_key|_normalise_key\\(" src/aeat/application src/aeat/domain/profile -g "*.py"` found no remaining application use of the private normalizer or private workflow re-export.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S12` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P03-S12.md src/aeat/domain/profile/_normalise.py src/aeat/domain/profile/__init__.py src/aeat/domain/profile/_keys.py src/aeat/domain/profile/test_normalise.py src/aeat/application/workflow/_utils.py src/aeat/application/review/_actions.py src/aeat/application/review/_models.py` passed with the existing plan-file CRLF normalization warning.
