---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-05-01-post-restructure-audit]]"
---

# `aeat-restructure` audit-3 google-split

Split Google OAuth/service helpers out of `adapters/outbound/aeat/auth/` into a
dedicated `adapters/outbound/google/` subpackage. No re-export shim per ADR
audit-3 directive.

## status

In progress.

## scope

- Created: `src/aeat/adapters/outbound/google/__init__.py`
- Created: `src/aeat/adapters/outbound/google/_paths.py`
- Created: `src/aeat/adapters/outbound/google/test_google.py`
- Deleted: `src/aeat/adapters/outbound/aeat/auth/_google_paths.py`
- Deleted: `src/aeat/core/_test_auth.py`
- Modified: `src/aeat/adapters/outbound/aeat/auth/__init__.py` — stripped of all Google symbols
- Updated: all consumer import sites across `entrypoints/`, `core/`, `application/`

## description

All Google-cluster symbols (`DRIVE_SCOPE`, `SHEETS_SCOPE`, `DOCS_SCOPE`,
`CLOUD_PLATFORM_SCOPE`, scope lists, `get_oauth_credentials`,
`get_service_account_credentials`, `get_credentials`, `get_credentials_for_scopes`,
`get_adc_credentials_with_scopes`, `assert_credentials_have_scopes`, all
`build_*_service`/`build_*_client` helpers, and the `GoogleAuthPath`,
`GoogleAuthInspection`, `inspect_google_auth`, `inspect_oauth_token_cache`,
`adc_well_known_path`, `normalize_google_auth_path` path-inspection types)
moved from `adapters/outbound/aeat/auth/` to the new canonical home
`adapters/outbound/google/`.

`_google_paths.py` was renamed to `google/_paths.py`. The colocated
test file `core/_test_auth.py` (which tests pure Google-inspection helpers)
was relocated to `google/test_google.py` with `pytestmark` updated from
`domain_core` to `domain_outbound`.

No shim was added. All 45+ import sites updated directly.

## tests

`pytest --collect-only` confirms zero `ImportError`. All unit tests pass.
Ruff and mypy run clean on modified files.
