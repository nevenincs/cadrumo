---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S15'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P05.S15`

Ran the focused closeout gate matrix for repair integrity, diagnostics, config/storage hygiene, root-fallback guards, registry validation, and locale catalogue health.

- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vault/audit/2026-05-22-secure-object-integrity-P05-S15-review.md`

## Description

The first S15 pass found two closeout issues. The locale honesty ratchet reported untranslated Catalan and Hungarian `wizard.test` labels that exceeded the current ceiling, and the ephemeral-key hygiene guard reported that the public repair privacy contract test used a default SQL-backed secure-object repository without declaring temp database isolation.

The locale issue was fixed by translating the affected Catalan and Hungarian wizard test labels. The storage hygiene issue was fixed by adding an autouse temp `AEAT_DATABASE_URL` fixture with engine disposal before and after the test, matching the accepted P02 isolation pattern while preserving real CLI and real encrypted SQL behavior.

The S15 review also noted existing registry-source scaffold self-reference values in Catalan and Hungarian locale files. That finding is catalogue cleanup debt outside the secure-object integrity attribution command and was recorded as low severity rather than treated as an S15 blocker.

## Tests

Focused gates passed:

- `uv run ruff check` over the touched repair, diagnostics, CLI, storage, locale, and registry verification files.
- `uv run python -m aeat.locales audit`
- `uv run python -m aeat.locales scaffold --check`
- `uv run pytest src/aeat/application/test_repair_integrity.py -q`
- `uv run pytest src/aeat/application/test_diagnostics.py -q`
- `uv run pytest src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py -q`
- `uv run pytest src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/tests/test_secure_sql.py src/aeat/core/test_storage_route_classification.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_referential_integrity.py -q`
- `uv run aeat --format json app registry verify --registry-root src/aeat/_data/registry/aeat --source-root src/aeat/_data`

Mandatory scoped review found no critical or high blockers.

Review audit: `2026-05-22-secure-object-integrity-P05-S15-review`.
