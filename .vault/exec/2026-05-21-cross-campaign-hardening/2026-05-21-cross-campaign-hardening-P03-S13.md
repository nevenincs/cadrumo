---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P03.S13'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P03.S13`

Closed XDOM-5: profile-binding selector extraction is now available
from the public `domain.user_profile` surface.

- Modified: `src/aeat/domain/user_profile/_registry_contract.py`
- Modified: `src/aeat/domain/user_profile/__init__.py`
- Modified: `src/aeat/domain/user_profile/test_registry_contract.py`
- Modified: `src/aeat/application/modelo/_profile_binding.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Promoted `_profile_binding_selectors` as public
`profile_binding_selectors`, exported it from `aeat.domain.user_profile`,
and re-pointed the modelo profile-binding resolver to the public
accessor. The private alias remains inside the registry-contract module
for compatibility, while internal and application call sites use the
public name.

Added direct public-surface coverage proving the accessor deduplicates
the supported selector forms.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/domain/user_profile/_registry_contract.py src/aeat/domain/user_profile/__init__.py src/aeat/domain/user_profile/test_registry_contract.py src/aeat/application/modelo/_profile_binding.py src/aeat/application/modelo/test_profile_binding.py` passed.

`uv run pytest -q src/aeat/domain/user_profile/test_registry_contract.py src/aeat/application/modelo/test_profile_binding.py` passed with 13 tests in 41.66s.

`rg -n "from .*domain\\.user_profile\\._registry_contract import _profile_binding_selectors|_profile_binding_selectors\\(" src/aeat/application src/aeat/domain/user_profile -g "*.py"` found no remaining private-selector imports or calls.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S13` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P03-S13.md src/aeat/domain/user_profile/_registry_contract.py src/aeat/domain/user_profile/__init__.py src/aeat/domain/user_profile/test_registry_contract.py src/aeat/application/modelo/_profile_binding.py` passed with existing CRLF normalization warnings for the plan file and `domain/user_profile/__init__.py`.
