---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W05.P15.S53'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W05.P15.S53 - URL Authority Conformance Gate

## Scope

- `src/aeat/core/external_constants.py`
- `src/aeat/core/external_constants.toml`
- `src/aeat/core/test_external_constants.py`
- `src/aeat/domain/portals`
- `src/aeat/tests/aeat_literal_fixtures.py`
- overview calendar tests that previously carried bare Sede URL literals

## Work

Centralized portal route authority through external constants:

- `PortalHost` now stores stable registry keys rather than raw hostnames.
- `_hosts.py` resolves portal host origins and hostnames through
  `Settings.external_constants().aeat.domains`.
- portal entry modules read their route paths through the centralized
  `aeat.portal_paths` registry.
- `PortalMetadata` validates host authority and active filing/censo path shape
  against the centralized registry.
- external-constants tests now guard portal host/path coverage and reject
  reintroduced AEAT/Sede route literals in portal entries and tests unless they
  are declared canaries.

## Verification

- `uv run --no-sync ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/tests/aeat_literal_fixtures.py src/aeat/domain/portals src/aeat/application/overview/test_calendar.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py`
- `uv run --no-sync pytest src/aeat/domain/portals`
- `uv run --no-sync pytest src/aeat/core/test_external_constants.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py`

## Outcome

Ruff passed for the touched authority surfaces. The portal test suite passed
with 60 tests. The external-constants and overview-calendar CLI gate passed
with 78 tests after replacing residual bare Sede URL literals in overview
calendar tests with declared literal fixtures.
