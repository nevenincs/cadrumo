---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P09.S37'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P09.S37`

Closed GEN-1 task 501.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/__init__.py`
- Modified: `src/aeat/application/user_profile/_censo_sync.py`
- Created: `src/aeat/adapters/outbound/aeat/sede/test_censo_live.py`
- Formatted: `src/aeat/adapters/outbound/aeat/sede/test_census_parser.py`

## Description

Promoted the G313 live census driver through the public
`aeat.adapters.outbound.aeat.sede` boundary and repointed
`CensoSyncService.refresh_census_from_sede` away from the private
`_censo_live` module import.

Split the browser-navigation branch behind a typed storage-state helper
so the live-gated Playwright fetch path can be exercised deterministically:
the test now verifies that the authenticated storage state is passed into
`create_context`, the G313 launcher is opened with
`wait_until="domcontentloaded"`, page HTML is parsed, and both context and
browser session are closed.

No live AEAT call was made; the actual live call remains guarded by
`AeatAccessGate.require_live_read()` in the service.

## Tests

`uv run ruff check src/aeat/adapters/outbound/aeat/sede/_censo_live.py src/aeat/adapters/outbound/aeat/sede/__init__.py src/aeat/application/user_profile/_censo_sync.py src/aeat/adapters/outbound/aeat/sede/test_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_census_parser.py src/aeat/application/user_profile/test_census_sync.py src/aeat/entrypoints/cli/test_profile_census_verbs.py` passed after applying ruff's import-format fix to `test_census_parser.py`.

`uv run ty check src/aeat/adapters/outbound/aeat/sede/_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_censo_live.py src/aeat/application/user_profile/_censo_sync.py` passed.

`uv run pytest src/aeat/application/user_profile/test_census_sync.py src/aeat/entrypoints/cli/test_profile_census_verbs.py src/aeat/adapters/outbound/aeat/sede/test_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_census_parser.py -q` passed with 29 tests in 16.07s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S37` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P09-S37.md src/aeat/adapters/outbound/aeat/sede/_censo_live.py src/aeat/adapters/outbound/aeat/sede/__init__.py src/aeat/application/user_profile/_censo_sync.py src/aeat/adapters/outbound/aeat/sede/test_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_census_parser.py` passed.
