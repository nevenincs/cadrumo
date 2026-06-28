---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

REPAIR-PROFILE-PRIVACY-001 | HIGH | `config repair profile` emitted raw profile identifiers

Review found that the repair-profile diagnostic path emitted raw active profile, profile id, and bucket id values in text and JSON output. The remediation redacts repair-profile health payload identifiers to `<profile-id>` and adds a real CLI privacy regression covering `config repair profile`, `config repair profile --profile`, and `config repair profile --repair-manifest-status --yes` in both text and JSON modes.

Validation:

- `uv run ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/locales/test_parity.py`
- `uv run pytest -q src/aeat/diagnostics/test_profile.py src/aeat/diagnostics/test_secure_objects.py src/aeat/entrypoints/cli/test_config_profile_surface_inventory.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/application/test_config_parity.py::test_retired_config_profile_set_is_not_registered`
- `uv run pytest -q src/aeat/locales/test_locale_translation_honesty.py src/aeat/locales/test_parity.py`
- `uv run -q python -m aeat.locales audit`

RETIRED-REPAIR-LIST-LOCALE-002 | LOW | Retired `config repair list` locale leaves remained after command removal

Review found stale `cli.config.repair.list_*` leaves in active locale catalogs after the operator command was retired. The leaves were removed via `python -m aeat.locales remove`; `aeat.locales audit` remains clean.
