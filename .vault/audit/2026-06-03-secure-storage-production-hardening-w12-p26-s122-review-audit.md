---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-10-03'
body_hash: 'sha256:2fc38d2d1a6739edebca84d97832daf8030b051cf3cb8bc104ca2ba3e0ab2243'
related: []
---

# W12.P26.S122 review

## Scope

This review covers `AFR-020` for
the retired module.

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

- the historical check
  - Result: 6 passed.
- the historical check
  - Result: all checks passed.
- the historical check
  - Result: no matches.

## Disposition

`AFR-020` can close as `remote-mirror`: the file is an outbound AEAT live-fetch
boundary and not a competing local storage backend.
