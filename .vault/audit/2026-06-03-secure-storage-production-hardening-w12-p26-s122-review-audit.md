---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S122]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P24-S98]]'
---

# W12.P26.S122 review

## Scope

This review covers `AFR-020` for
`src/aeat/adapters/outbound/aeat/sede/_censo_live.py`.

## Findings

S122-001 | PASS | `_censo_live.py` is an outbound live-call adapter

The file uses authenticated AEAT browser storage state to navigate to the G313 censo
launcher, parse returned HTML into `CensoFactSet`, and project facts into application
snapshot keys. It does not write local files, select storage providers, construct
secure-object repositories, or route SQL/settings-backed persistence.

S122-002 | PASS | Settings, localization, and exception boundaries are respected

The G313 URL is derived from `Settings.external_constants()`. The public fetch function
accepts optional `Settings`, passes settings to the browser-session factory, and raises
`SedeNavigationError` with `tr("adapters.sede.errors.no_auth_session")` for the
user-facing no-session path.

## Validation

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/sede/test_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_playwright_wait_constants.py`
  - Result: 6 passed.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/sede/_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_playwright_wait_constants.py`
  - Result: all checks passed.
- `rg -n "SecureObjectRepository|SecureBoundRepository|StorageProvider|GoogleDrive|LocalStorage|write_text\(|read_text\(|write_bytes\(|open\(|storage_path|aeat_database_url|override_settings|os\.environ|getenv" src/aeat/adapters/outbound/aeat/sede/_censo_live.py`
  - Result: no matches.

## Disposition

`AFR-020` can close as `remote-mirror`: the file is an outbound AEAT live-fetch
boundary and not a competing local storage backend.
