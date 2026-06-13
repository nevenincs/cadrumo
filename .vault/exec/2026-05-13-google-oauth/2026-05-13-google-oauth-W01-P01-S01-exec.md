---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'S01'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01.S01`

Add the three direct runtime dependencies required by the v1 OAuth Desktop flow + Drive/Sheets integration per ADR-0 §3.

- Modified: `pyproject.toml` (added `google-auth>=2.50.0`, `google-auth-oauthlib>=1.3.1`, `google-api-python-client>=2.195.0` with rationale comment)
- Modified: `uv.lock` (resolved transitives: google-api-core, googleapis-common-protos, httplib2, oauthlib, proto-plus, pyasn1, pyasn1-modules, pyparsing, requests-oauthlib, uritemplate, google-auth-httplib2)

## Description

Three direct dependencies, locked to versions meeting the ADR's minimums:

- `google-auth 2.52.0` — credentials primitive + refresh logic. Successor to the previously-pinned 2.49.x baseline; minor API changes only.
- `google-auth-oauthlib 1.4.0` — Desktop OAuth client `InstalledAppFlow.run_local_server` (loopback IP + PKCE).
- `google-api-python-client 2.196.0` — Drive v3 + Sheets v4 discovery clients.

`google-auth-httplib2 0.4.0` resolves as a transitive of `google-api-python-client`. It is not pinned directly per ADR-0's "Explicitly not added" list — upstream archived in 2026-03 and our transport story relies on `requests` (also transitive via `google-auth`).

The other ADR-0 exclusions (`gspread`, `google-cloud-functions`, `google-cloud-run`, `google-cloud-storage`) remain absent.

## Tests

- `uv lock` resolved 208 packages with no version conflicts; 14 packages newly introduced.
- No source code consumes the new packages yet; runtime tests deferred to S03 / S05 / S08.
